"""Append-only audit log with hash chain.

This is the **core integrity guarantee** of PGO.

How it works
------------
1. Every state transition produces a :class:`TransitionEvent`.
2. ``append()`` serialises the event canonically (sorted JSON, no spaces).
3. Computes ``entry_hash = SHA-256(canonical_blob + prev_hash)``.
4. Inserts an immutable row into the ``events`` table.
5. Never updates or deletes rows.

Verification
------------
``verify_chain()`` reads all events in sequence order, recomputes each
hash, and checks that ``entry_hash`` matches.  If any row was edited
inside SQLite (or a row was deleted/inserted out of order), the chain
breaks and :class:`AuditChainBroken` is raised.

Export
------
``export_audit()`` returns the full event log as a list of dicts,
suitable for JSON/CSV serialisation.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3

import structlog

from pgo.core.errors import AuditChainBroken
from pgo.state import TransitionEvent

logger = structlog.get_logger()


def append(conn: sqlite3.Connection, event: TransitionEvent, *, notes: str = "") -> str:
    """Append an event to the audit log and return its ``entry_hash``.

    Parameters
    ----------
    conn:
        Database connection (from :func:`pgo.core.db.open_db`).
    event:
        The transition event to record.
    notes:
        Optional free-text annotation (will be stored but NOT included
        in the hash — so annotations can be added without breaking the chain).

    Returns
    -------
    str
        The SHA-256 hex digest of this entry.
    """
    prev_hash = _get_last_hash(conn)

    canonical = _canonical_blob(event)
    entry_hash = hashlib.sha256((canonical + prev_hash).encode("utf-8")).hexdigest()

    conn.execute(
        """
        INSERT INTO events (finding_id, from_status, to_status, at_utc, entry_hash, prev_hash, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event.finding_id,
            event.from_status.value,
            event.to_status.value,
            event.at_utc,
            entry_hash,
            prev_hash,
            notes,
        ),
    )
    conn.commit()

    logger.info(
        "audit_event_appended",
        finding_id=event.finding_id,
        transition=f"{event.from_status.value}→{event.to_status.value}",
        entry_hash=entry_hash[:12],
        seq=conn.execute("SELECT last_insert_rowid()").fetchone()[0],
    )
    return entry_hash


def verify_chain(conn: sqlite3.Connection) -> int:
    """Verify the full hash chain.  Returns the number of events checked.

    Raises
    ------
    AuditChainBroken
        If any hash does not match the recomputed value.
    """
    rows = conn.execute(
        "SELECT seq, finding_id, from_status, to_status, at_utc, entry_hash, prev_hash "
        "FROM events ORDER BY seq"
    ).fetchall()

    expected_prev = ""
    checked = 0

    for row in rows:
        seq = row["seq"]
        stored_hash = row["entry_hash"]
        stored_prev = row["prev_hash"]

        # Verify prev_hash linkage.
        if stored_prev != expected_prev:
            raise AuditChainBroken(
                f"Chain broken at seq={seq}: expected prev_hash={expected_prev[:12]}... "
                f"but found {stored_prev[:12]}..."
            )

        # Recompute entry_hash from event data.
        event = TransitionEvent(
            finding_id=row["finding_id"],
            from_status=row["from_status"],
            to_status=row["to_status"],
            at_utc=row["at_utc"],
        )
        canonical = _canonical_blob(event)
        recomputed = hashlib.sha256((canonical + stored_prev).encode("utf-8")).hexdigest()

        if recomputed != stored_hash:
            raise AuditChainBroken(
                f"Tamper detected at seq={seq}: recomputed hash={recomputed[:12]}... "
                f"does not match stored={stored_hash[:12]}..."
            )

        expected_prev = stored_hash
        checked += 1

    logger.info("audit_chain_verified", events_checked=checked)
    return checked


def export_audit(conn: sqlite3.Connection) -> list[dict[str, str | int]]:
    """Export the full audit log as a list of dicts (for JSON/CSV).

    Returns
    -------
    list[dict]
        Each dict has keys: seq, finding_id, from_status, to_status,
        at_utc, entry_hash, prev_hash, notes.
    """
    rows = conn.execute(
        "SELECT seq, finding_id, from_status, to_status, at_utc, "
        "entry_hash, prev_hash, notes FROM events ORDER BY seq"
    ).fetchall()
    return [dict(row) for row in rows]


# ── Internal helpers ────────────────────────────────────────

def _canonical_blob(event: TransitionEvent) -> str:
    """Deterministic JSON serialisation of an event.

    Sorted keys, no whitespace — so the same event always produces the
    same string regardless of Python dict ordering or formatting.

    Uses ``.value`` for enum fields to guarantee the same output whether
    the field is a :class:`FindingStatus` or a plain string (as happens
    when reconstructing events from DB rows during verification).
    """
    from_val = event.from_status.value if hasattr(event.from_status, "value") else event.from_status
    to_val = event.to_status.value if hasattr(event.to_status, "value") else event.to_status
    obj = {
        "at_utc": event.at_utc,
        "finding_id": event.finding_id,
        "from_status": from_val,
        "to_status": to_val,
    }
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def _get_last_hash(conn: sqlite3.Connection) -> str:
    """Return the ``entry_hash`` of the most recent event, or ``""`` for the first."""
    row = conn.execute(
        "SELECT entry_hash FROM events ORDER BY seq DESC LIMIT 1"
    ).fetchone()
    return row["entry_hash"] if row else ""
