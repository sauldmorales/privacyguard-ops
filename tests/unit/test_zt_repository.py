"""Tests for Zero Trust input validation at the repository boundary.

Ensures the repository layer rejects malicious inputs that would have
bypassed a naive CLI layer. This is defence-in-depth: even if the CLI
validation is skipped (e.g. programmatic usage), the domain layer
still validates.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from pgo.core.db import open_db
from pgo.core.repository import create_finding, get_finding, transition_finding
from pgo.core.models import FindingStatus


@pytest.fixture()
def conn(tmp_path: Path) -> sqlite3.Connection:  # type: ignore[misc]
    c = open_db(tmp_path / "zt_test.db")
    yield c  # type: ignore[misc]
    c.close()


class TestRepositoryInputValidation:
    """Validate that repository functions reject malicious inputs."""

    def test_rejects_sql_injection_finding_id(self, conn: sqlite3.Connection) -> None:
        with pytest.raises(ValueError, match="invalid characters"):
            create_finding(conn, finding_id="'; DROP TABLE findings;--", broker_name="Test")

    def test_rejects_sql_injection_broker(self, conn: sqlite3.Connection) -> None:
        with pytest.raises(ValueError, match="invalid characters"):
            create_finding(conn, finding_id="f-1", broker_name="'; DELETE FROM events;--")

    def test_rejects_path_traversal_url(self, conn: sqlite3.Connection) -> None:
        with pytest.raises(ValueError, match="http/https"):
            create_finding(conn, finding_id="f-1", broker_name="Test", url="file:///etc/passwd")

    def test_rejects_javascript_url(self, conn: sqlite3.Connection) -> None:
        with pytest.raises(ValueError, match="http/https"):
            create_finding(conn, finding_id="f-1", broker_name="Test", url="javascript:alert(1)")

    def test_rejects_empty_finding_id(self, conn: sqlite3.Connection) -> None:
        with pytest.raises(ValueError, match="must not be empty"):
            create_finding(conn, finding_id="", broker_name="Test")

    def test_rejects_empty_broker(self, conn: sqlite3.Connection) -> None:
        with pytest.raises(ValueError, match="must not be empty"):
            create_finding(conn, finding_id="f-1", broker_name="")

    def test_accepts_valid_inputs(self, conn: sqlite3.Connection) -> None:
        f = create_finding(conn, finding_id="f-1", broker_name="BeenVerified", url="https://beenverified.com")
        assert f.finding_id == "f-1"
        assert f.broker_name == "BeenVerified"

    def test_get_finding_validates_id(self, conn: sqlite3.Connection) -> None:
        with pytest.raises(ValueError, match="invalid characters"):
            get_finding(conn, "'; DROP TABLE findings;--")

    def test_transition_validates_id(self, conn: sqlite3.Connection) -> None:
        with pytest.raises(ValueError, match="invalid characters"):
            transition_finding(conn, "'; DROP TABLE findings;--", FindingStatus.CONFIRMED)
