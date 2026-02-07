"""Tests for pgo.core.db — SQLite manager."""

from pathlib import Path

import pytest

from pgo.core.db import SCHEMA_VERSION, open_db


@pytest.fixture()
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "test.db"


class TestOpenDb:
    """open_db creates schema, enables WAL + FK, is idempotent."""

    def test_creates_file(self, db_path: Path) -> None:
        conn = open_db(db_path)
        assert db_path.exists()
        conn.close()

    def test_wal_mode(self, db_path: Path) -> None:
        conn = open_db(db_path)
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode == "wal"
        conn.close()

    def test_foreign_keys_on(self, db_path: Path) -> None:
        conn = open_db(db_path)
        fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
        assert fk == 1
        conn.close()

    def test_schema_version_stored(self, db_path: Path) -> None:
        conn = open_db(db_path)
        row = conn.execute(
            "SELECT value FROM meta WHERE key = 'schema_version'"
        ).fetchone()
        assert row is not None
        assert row["value"] == str(SCHEMA_VERSION)
        conn.close()

    def test_tables_created(self, db_path: Path) -> None:
        conn = open_db(db_path)
        tables = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert "findings" in tables
        assert "events" in tables
        assert "meta" in tables
        conn.close()

    def test_idempotent(self, db_path: Path) -> None:
        """Calling open_db twice on the same file should not error."""
        conn1 = open_db(db_path)
        conn1.close()
        conn2 = open_db(db_path)
        # Should still have all tables
        tables = {
            row["name"]
            for row in conn2.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert "findings" in tables
        conn2.close()

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        nested = tmp_path / "a" / "b" / "deep.db"
        conn = open_db(nested)
        assert nested.exists()
        conn.close()

    def test_row_factory_returns_dict_like(self, db_path: Path) -> None:
        conn = open_db(db_path)
        conn.execute("INSERT INTO meta(key, value) VALUES ('test_key', 'hello')")
        row = conn.execute("SELECT * FROM meta WHERE key = 'test_key'").fetchone()
        # sqlite3.Row supports key-based access
        assert row["key"] == "test_key"
        assert row["value"] == "hello"
        conn.close()
