"""Findings repository — CRUD for broker profiles.

Thin wrapper around SQLite that enforces the state machine rules.
Every state change goes through ``transition_finding()``, which:

1. Validates the transition via ``state.can_transition()``.
2. Writes the new status to the ``findings`` table.
3. Returns a ``TransitionEvent`` (which the caller passes to the audit log).

This module never touches the events table directly — that's ``audit.py``'s job.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone

from pgo.core.errors import StateTransitionInvalid
from pgo.core.models import FindingStatus
from pgo.core.state import can_transition, TransitionEvent
from pgo.modules.pii_guard import validate_broker_name, validate_finding_id, validate_url


@dataclass(frozen=True)
class Finding:
    """A broker profile being tracked."""

    finding_id: str
    broker_name: str
    url: str | None
    status: FindingStatus
    created_utc: str
    updated_utc: str


def create_finding(
    conn: sqlite3.Connection,
    *,
    finding_id: str,
    broker_name: str,
    url: str | None = None,
) -> Finding:
    """Insert a new finding in ``discovered`` state.

    All inputs are validated through the PII guard before touching SQLite.

    Returns the created :class:`Finding`.

    Raises
    ------
    ValueError
        If any input fails whitelist validation.
    """
    finding_id = validate_finding_id(finding_id)
    broker_name = validate_broker_name(broker_name)
    url = validate_url(url)
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """
        INSERT INTO findings (finding_id, broker_name, url, status, created_utc, updated_utc)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (finding_id, broker_name, url, FindingStatus.DISCOVERED.value, now, now),
    )
    conn.commit()
    return Finding(
        finding_id=finding_id,
        broker_name=broker_name,
        url=url,
        status=FindingStatus.DISCOVERED,
        created_utc=now,
        updated_utc=now,
    )


def get_finding(conn: sqlite3.Connection, finding_id: str) -> Finding | None:
    """Fetch a single finding by ID, or ``None`` if not found."""
    finding_id = validate_finding_id(finding_id)
    row = conn.execute(
        "SELECT * FROM findings WHERE finding_id = ?", (finding_id,)
    ).fetchone()
    if row is None:
        return None
    return _row_to_finding(row)


def list_findings(conn: sqlite3.Connection) -> list[Finding]:
    """Return all findings, ordered by creation date."""
    rows = conn.execute(
        "SELECT * FROM findings ORDER BY created_utc"
    ).fetchall()
    return [_row_to_finding(r) for r in rows]


def transition_finding(
    conn: sqlite3.Connection,
    finding_id: str,
    to_status: FindingStatus,
) -> TransitionEvent:
    """Move a finding to a new status.

    Validates the transition, updates the row, and returns a
    :class:`TransitionEvent` for the audit log.

    Raises
    ------
    KeyError
        If the finding does not exist.
    StateTransitionInvalid
        If the transition is not allowed.
    """
    finding_id = validate_finding_id(finding_id)
    finding = get_finding(conn, finding_id)
    if finding is None:
        raise KeyError(f"Finding not found: {finding_id}")

    from_status = finding.status
    if not can_transition(from_status, to_status):
        raise StateTransitionInvalid(from_status.value, to_status.value)

    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "UPDATE findings SET status = ?, updated_utc = ? WHERE finding_id = ?",
        (to_status.value, now, finding_id),
    )
    conn.commit()

    return TransitionEvent(
        finding_id=finding_id,
        from_status=from_status,
        to_status=to_status,
        at_utc=now,
    )


def _row_to_finding(row: sqlite3.Row) -> Finding:
    return Finding(
        finding_id=row["finding_id"],
        broker_name=row["broker_name"],
        url=row["url"],
        status=FindingStatus(row["status"]),
        created_utc=row["created_utc"],
        updated_utc=row["updated_utc"],
    )
