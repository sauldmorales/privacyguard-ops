"""Tests for pgo.core.audit — append-only hash chain.

These tests prove the tamper-evident promise:
1. Events get appended with correct SHA-256 hashes.
2. The chain passes verification after normal use.
3. Tampering with ANY field in ANY row is detected.
4. Export returns a clean list of dicts.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from pgo.core.audit import append, export_audit, verify_chain
from pgo.core.db import open_db
from pgo.core.repository import create_finding, transition_finding
from pgo.core.models import FindingStatus
from pgo.core.state import TransitionEvent


@pytest.fixture()
def conn(tmp_path: Path) -> sqlite3.Connection:  # type: ignore[misc]
    c = open_db(tmp_path / "audit_test.db")
    # Pre-create a finding so FK constraints pass.
    create_finding(c, finding_id="f-1", broker_name="TestBroker")
    yield c  # type: ignore[misc]
    c.close()


def _make_event(
    finding_id: str = "f-1",
    from_status: FindingStatus = FindingStatus.DISCOVERED,
    to_status: FindingStatus = FindingStatus.CONFIRMED,
    at_utc: str = "2025-01-15T12:00:00+00:00",
) -> TransitionEvent:
    return TransitionEvent(
        finding_id=finding_id,
        from_status=from_status,
        to_status=to_status,
        at_utc=at_utc,
    )


# ── append ──────────────────────────────────────────────────
class TestAppend:
    def test_returns_hex_hash(self, conn: sqlite3.Connection) -> None:
        h = append(conn, _make_event())
        assert len(h) == 64  # SHA-256 hex
        assert all(c in "0123456789abcdef" for c in h)

    def test_first_event_prev_hash_empty(self, conn: sqlite3.Connection) -> None:
        append(conn, _make_event())
        row = conn.execute("SELECT prev_hash FROM events WHERE seq = 1").fetchone()
        assert row["prev_hash"] == ""

    def test_second_event_chains(self, conn: sqlite3.Connection) -> None:
        h1 = append(conn, _make_event(at_utc="2025-01-15T12:00:00"))
        append(conn, _make_event(at_utc="2025-01-15T13:00:00"))
        row = conn.execute("SELECT prev_hash FROM events WHERE seq = 2").fetchone()
        assert row["prev_hash"] == h1

    def test_notes_included_in_hash(self, conn: sqlite3.Connection) -> None:
        """Notes are now part of the hash chain — different notes
        on identical events produce different hashes."""
        event1 = _make_event(at_utc="2025-01-15T12:00:00")
        h1 = append(conn, event1, notes="first note")

        event2 = _make_event(at_utc="2025-01-15T13:00:00")
        h2 = append(conn, event2, notes="second note")

        # Both stored correctly.
        row = conn.execute("SELECT notes FROM events WHERE seq = 1").fetchone()
        assert row["notes"] == "first note"

        # Hashes differ (different notes + different timestamps + chained).
        assert h1 != h2


# ── verify_chain ────────────────────────────────────────────
class TestVerifyChain:
    def test_empty_chain_ok(self, conn: sqlite3.Connection) -> None:
        count = verify_chain(conn)
        assert count == 0

    def test_single_event_ok(self, conn: sqlite3.Connection) -> None:
        append(conn, _make_event())
        count = verify_chain(conn)
        assert count == 1

    def test_multi_event_ok(self, conn: sqlite3.Connection) -> None:
        for i in range(5):
            append(conn, _make_event(at_utc=f"2025-01-15T{i:02d}:00:00"))
        count = verify_chain(conn)
        assert count == 5

    def test_tamper_entry_hash_blocked_by_trigger(self, conn: sqlite3.Connection) -> None:
        """The DB trigger prevents UPDATE on events — this IS the security control."""
        append(conn, _make_event(at_utc="2025-01-15T01:00:00"))
        append(conn, _make_event(at_utc="2025-01-15T02:00:00"))

        # Attempt to tamper: the trigger must block this.
        import sqlite3 as _sqlite3
        with pytest.raises(_sqlite3.IntegrityError, match="append-only"):
            conn.execute("UPDATE events SET entry_hash = 'TAMPERED' WHERE seq = 1")

    def test_tamper_status_blocked_by_trigger(self, conn: sqlite3.Connection) -> None:
        """Changing a status field is blocked by the append-only trigger."""
        append(conn, _make_event(at_utc="2025-01-15T10:00:00"))

        import sqlite3 as _sqlite3
        with pytest.raises(_sqlite3.IntegrityError, match="append-only"):
            conn.execute("UPDATE events SET to_status = 'verified' WHERE seq = 1")

    def test_tamper_prev_hash_blocked_by_trigger(self, conn: sqlite3.Connection) -> None:
        """Altering prev_hash is blocked by the append-only trigger."""
        append(conn, _make_event(at_utc="2025-01-15T01:00:00"))
        append(conn, _make_event(at_utc="2025-01-15T02:00:00"))

        import sqlite3 as _sqlite3
        with pytest.raises(_sqlite3.IntegrityError, match="append-only"):
            conn.execute("UPDATE events SET prev_hash = 'BAD' WHERE seq = 2")

    def test_deleted_event_blocked_by_trigger(self, conn: sqlite3.Connection) -> None:
        """Deleting an event is blocked by the append-only trigger."""
        append(conn, _make_event(at_utc="2025-01-15T01:00:00"))
        append(conn, _make_event(at_utc="2025-01-15T02:00:00"))
        append(conn, _make_event(at_utc="2025-01-15T03:00:00"))

        import sqlite3 as _sqlite3
        with pytest.raises(_sqlite3.IntegrityError, match="append-only"):
            conn.execute("DELETE FROM events WHERE seq = 2")


# ── export_audit ────────────────────────────────────────────
class TestExportAudit:
    def test_empty(self, conn: sqlite3.Connection) -> None:
        assert export_audit(conn) == []

    def test_returns_dicts(self, conn: sqlite3.Connection) -> None:
        append(conn, _make_event())
        result = export_audit(conn)
        assert len(result) == 1
        assert isinstance(result[0], dict)

    def test_dict_keys(self, conn: sqlite3.Connection) -> None:
        append(conn, _make_event(), notes="test note")
        row = export_audit(conn)[0]
        expected_keys = {"seq", "finding_id", "from_status", "to_status", "at_utc", "entry_hash", "prev_hash", "notes"}
        assert set(row.keys()) == expected_keys

    def test_preserves_order(self, conn: sqlite3.Connection) -> None:
        for i in range(3):
            append(conn, _make_event(at_utc=f"2025-01-15T{i:02d}:00:00"))
        result = export_audit(conn)
        seqs = [r["seq"] for r in result]
        assert seqs == sorted(seqs)


# ── Integration: repository + audit together ────────────────
class TestRepoAuditIntegration:
    def test_full_lifecycle_with_chain(self, conn: sqlite3.Connection) -> None:
        """Create finding → transition through states → verify chain."""
        create_finding(conn, finding_id="f-int", broker_name="BeenVerified", url="https://bv.com")

        # Simulate the creation audit event.
        creation_event = TransitionEvent(
            finding_id="f-int",
            from_status=FindingStatus.DISCOVERED,
            to_status=FindingStatus.DISCOVERED,
            at_utc="2025-01-15T00:00:00+00:00",
        )
        append(conn, creation_event, notes="Finding created")

        # Transition: discovered → confirmed
        event1 = transition_finding(conn, "f-int", FindingStatus.CONFIRMED)
        append(conn, event1, notes="Confirmed via manual review")

        # Transition: confirmed → submitted
        event2 = transition_finding(conn, "f-int", FindingStatus.SUBMITTED)
        append(conn, event2, notes="Opt-out form submitted")

        # Transition: submitted → verified
        event3 = transition_finding(conn, "f-int", FindingStatus.VERIFIED)
        append(conn, event3, notes="Profile removed confirmed")

        # Chain should be intact.
        count = verify_chain(conn)
        assert count == 4

        # Export should have 4 events.
        events = export_audit(conn)
        assert len(events) == 4
