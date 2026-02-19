"""SQLite database manager.

Owns the connection lifecycle, schema creation, and migration.
Every other module that needs the DB receives the connection from here — 
they never open their own.

Design decisions
----------------
* WAL mode for concurrent reads.
* Foreign keys enforced.
* ``CREATE TABLE IF NOT EXISTS`` — idempotent, safe to call on every start.
* All writes inside explicit transactions (atomicity).
"""

from __future__ import annotations

import sqlite3
import stat
from pathlib import Path

import structlog

logger = structlog.get_logger()

# ── Schema version (bump when tables change) ────────────────
SCHEMA_VERSION = 1

_SCHEMA_SQL = """\
-- Findings: each broker profile being tracked
CREATE TABLE IF NOT EXISTS findings (
    finding_id   TEXT PRIMARY KEY,
    broker_name  TEXT NOT NULL,
    url          TEXT,
    status       TEXT NOT NULL DEFAULT 'discovered',
    created_utc  TEXT NOT NULL,
    updated_utc  TEXT NOT NULL
);

-- Append-only event log (the audit trail)
CREATE TABLE IF NOT EXISTS events (
    seq          INTEGER PRIMARY KEY AUTOINCREMENT,
    finding_id   TEXT    NOT NULL,
    from_status  TEXT    NOT NULL,
    to_status    TEXT    NOT NULL,
    at_utc       TEXT    NOT NULL,
    entry_hash   TEXT    NOT NULL,
    prev_hash    TEXT    NOT NULL DEFAULT '',
    notes        TEXT    NOT NULL DEFAULT '',
    FOREIGN KEY (finding_id) REFERENCES findings(finding_id)
);

-- Schema metadata
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- ── Append-only enforcement (Zero Trust) ──────────────────
-- These triggers make the events table truly immutable at the DB level.
-- Even if application code is compromised, the DB engine itself blocks
-- any UPDATE or DELETE on the audit trail.
CREATE TRIGGER IF NOT EXISTS events_no_update
    BEFORE UPDATE ON events
    BEGIN
        SELECT RAISE(ABORT, 'events table is append-only: UPDATE blocked');
    END;

CREATE TRIGGER IF NOT EXISTS events_no_delete
    BEFORE DELETE ON events
    BEGIN
        SELECT RAISE(ABORT, 'events table is append-only: DELETE blocked');
    END;
"""


def open_db(db_path: Path) -> sqlite3.Connection:
    """Open (or create) the PGO database and ensure the schema exists.

    Parameters
    ----------
    db_path:
        Absolute path to the SQLite file (e.g. ``data/pgo.db``).

    Returns
    -------
    sqlite3.Connection
        Ready-to-use connection with WAL mode and foreign keys enabled.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path), isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    # Create tables idempotently.
    conn.executescript(_SCHEMA_SQL)

    # Track schema version.
    conn.execute(
        "INSERT OR IGNORE INTO meta(key, value) VALUES (?, ?)",
        ("schema_version", str(SCHEMA_VERSION)),
    )
    conn.commit()

    # Harden file permissions: owner read/write only (Zero Trust).
    try:
        db_path.chmod(stat.S_IRUSR | stat.S_IWUSR)
        # Also harden the WAL and SHM files if they exist.
        for suffix in ("-wal", "-shm"):
            wal = db_path.parent / (db_path.name + suffix)
            if wal.exists():
                wal.chmod(stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        # Best effort — may fail on non-POSIX systems.
        pass

    logger.debug("database_opened", path=str(db_path), schema_version=SCHEMA_VERSION)
    return conn
