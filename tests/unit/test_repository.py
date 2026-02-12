"""Tests for pgo.core.repository — Findings CRUD + state transitions."""

from pathlib import Path

import pytest

from pgo.core.db import open_db
from pgo.core.errors import StateTransitionInvalid
from pgo.core.repository import (
    Finding,
    create_finding,
    get_finding,
    list_findings,
    transition_finding,
)
from pgo.core.models import FindingStatus


@pytest.fixture()
def conn(tmp_path: Path):
    """Yield a fresh in-memory-like DB connection."""
    c = open_db(tmp_path / "test.db")
    yield c
    c.close()


# ── create_finding ──────────────────────────────────────────
class TestCreateFinding:
    def test_creates_in_discovered(self, conn) -> None:
        f = create_finding(conn, finding_id="f-1", broker_name="BeenVerified")
        assert f.status == FindingStatus.DISCOVERED
        assert f.finding_id == "f-1"
        assert f.broker_name == "BeenVerified"

    def test_creates_with_url(self, conn) -> None:
        f = create_finding(conn, finding_id="f-2", broker_name="Spokeo", url="https://spokeo.com/remove")
        assert f.url == "https://spokeo.com/remove"

    def test_creates_without_url(self, conn) -> None:
        f = create_finding(conn, finding_id="f-3", broker_name="WhitePages")
        assert f.url is None

    def test_duplicate_id_raises(self, conn) -> None:
        create_finding(conn, finding_id="f-dup", broker_name="A")
        with pytest.raises(Exception):  # sqlite3.IntegrityError
            create_finding(conn, finding_id="f-dup", broker_name="B")

    def test_timestamps_are_set(self, conn) -> None:
        f = create_finding(conn, finding_id="f-ts", broker_name="X")
        assert f.created_utc != ""
        assert f.updated_utc != ""


# ── get_finding ─────────────────────────────────────────────
class TestGetFinding:
    def test_found(self, conn) -> None:
        create_finding(conn, finding_id="f-g1", broker_name="Intelius")
        found = get_finding(conn, "f-g1")
        assert found is not None
        assert found.broker_name == "Intelius"

    def test_not_found(self, conn) -> None:
        assert get_finding(conn, "nonexistent") is None


# ── list_findings ───────────────────────────────────────────
class TestListFindings:
    def test_empty(self, conn) -> None:
        assert list_findings(conn) == []

    def test_ordered_by_created(self, conn) -> None:
        create_finding(conn, finding_id="f-a", broker_name="A")
        create_finding(conn, finding_id="f-b", broker_name="B")
        create_finding(conn, finding_id="f-c", broker_name="C")
        result = list_findings(conn)
        assert [f.finding_id for f in result] == ["f-a", "f-b", "f-c"]

    def test_returns_finding_objects(self, conn) -> None:
        create_finding(conn, finding_id="f-obj", broker_name="Obj")
        result = list_findings(conn)
        assert isinstance(result[0], Finding)


# ── transition_finding ──────────────────────────────────────
class TestTransitionFinding:
    def test_discovered_to_confirmed(self, conn) -> None:
        create_finding(conn, finding_id="f-t1", broker_name="T1")
        event = transition_finding(conn, "f-t1", FindingStatus.CONFIRMED)
        assert event.from_status == FindingStatus.DISCOVERED
        assert event.to_status == FindingStatus.CONFIRMED
        # DB row is updated.
        f = get_finding(conn, "f-t1")
        assert f is not None
        assert f.status == FindingStatus.CONFIRMED

    def test_confirmed_to_submitted(self, conn) -> None:
        create_finding(conn, finding_id="f-t2", broker_name="T2")
        transition_finding(conn, "f-t2", FindingStatus.CONFIRMED)
        event = transition_finding(conn, "f-t2", FindingStatus.SUBMITTED)
        assert event.from_status == FindingStatus.CONFIRMED
        assert event.to_status == FindingStatus.SUBMITTED

    def test_full_happy_path(self, conn) -> None:
        """DISCOVERED → CONFIRMED → SUBMITTED → PENDING → VERIFIED."""
        create_finding(conn, finding_id="f-hp", broker_name="HP")
        transition_finding(conn, "f-hp", FindingStatus.CONFIRMED)
        transition_finding(conn, "f-hp", FindingStatus.SUBMITTED)
        transition_finding(conn, "f-hp", FindingStatus.PENDING)
        transition_finding(conn, "f-hp", FindingStatus.VERIFIED)
        f = get_finding(conn, "f-hp")
        assert f is not None
        assert f.status == FindingStatus.VERIFIED

    def test_invalid_transition_raises(self, conn) -> None:
        create_finding(conn, finding_id="f-bad", broker_name="Bad")
        with pytest.raises(StateTransitionInvalid):
            transition_finding(conn, "f-bad", FindingStatus.VERIFIED)

    def test_nonexistent_finding_raises(self, conn) -> None:
        with pytest.raises(KeyError, match="not found"):
            transition_finding(conn, "ghost", FindingStatus.CONFIRMED)

    def test_resurfaced_resubmit(self, conn) -> None:
        """VERIFIED → RESURFACED → SUBMITTED (re-submit cycle)."""
        create_finding(conn, finding_id="f-re", broker_name="Re")
        transition_finding(conn, "f-re", FindingStatus.CONFIRMED)
        transition_finding(conn, "f-re", FindingStatus.SUBMITTED)
        transition_finding(conn, "f-re", FindingStatus.VERIFIED)
        transition_finding(conn, "f-re", FindingStatus.RESURFACED)
        event = transition_finding(conn, "f-re", FindingStatus.SUBMITTED)
        assert event.from_status == FindingStatus.RESURFACED
        assert event.to_status == FindingStatus.SUBMITTED

    def test_event_has_timestamp(self, conn) -> None:
        create_finding(conn, finding_id="f-ev", broker_name="Ev")
        event = transition_finding(conn, "f-ev", FindingStatus.CONFIRMED)
        assert event.at_utc != ""
        assert "T" in event.at_utc  # ISO format
