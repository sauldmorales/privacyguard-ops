"""Tests for pgo.modules.vault — evidence encryption/decryption.

Zero Trust tests:
1. Store + retrieve round-trip with integrity check.
2. Wrong key fails decryption.
3. Missing key raises VaultKeyMissing.
4. Oversized evidence is rejected.
5. Empty evidence is rejected.
6. File permissions are restricted.
"""

from __future__ import annotations

import stat
from pathlib import Path

import pytest

from pgo.core.errors import VaultKeyMissing, VaultWriteFailed

# Skip all tests if cryptography is not installed.
cryptography = pytest.importorskip("cryptography")

from pgo.modules.vault import (  # noqa: E402
    compute_integrity_hash,
    harden_directory_permissions,
    retrieve_evidence,
    store_evidence,
)


@pytest.fixture(autouse=True)
def _vault_key(monkeypatch: pytest.MonkeyPatch) -> None:  # pyright: ignore[reportUnusedFunction]
    """Set a vault key for all tests (auto-applied)."""
    monkeypatch.setenv("PGO_VAULT_KEY", "test-secret-key-for-unit-tests")


@pytest.fixture()
def vault_dir(tmp_path: Path) -> Path:
    d = tmp_path / "vault"
    d.mkdir()
    return d


# ── Round-trip ─────────────────────────────────────────────
class TestStoreRetrieve:
    def test_round_trip(self, vault_dir: Path) -> None:
        data = b"Screenshot evidence bytes"
        meta = store_evidence(vault_dir, "f-1", data)
        assert meta["finding_id"] == "f-1"
        assert "integrity_hash" in meta
        assert "path" in meta

        recovered = retrieve_evidence(
            vault_dir, "f-1", expected_hash=meta["integrity_hash"]
        )
        assert recovered == data

    def test_integrity_hash_deterministic(self) -> None:
        h1 = compute_integrity_hash(b"hello")
        h2 = compute_integrity_hash(b"hello")
        assert h1 == h2

    def test_different_data_different_hash(self) -> None:
        assert compute_integrity_hash(b"a") != compute_integrity_hash(b"b")


# ── Error cases ────────────────────────────────────────────
class TestVaultErrors:
    def test_missing_key(self, vault_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("PGO_VAULT_KEY", raising=False)
        with pytest.raises(VaultKeyMissing):
            store_evidence(vault_dir, "f-1", b"data")

    def test_empty_evidence(self, vault_dir: Path) -> None:
        with pytest.raises(VaultWriteFailed, match="empty"):
            store_evidence(vault_dir, "f-1", b"")

    def test_oversized_evidence(self, vault_dir: Path) -> None:
        big = b"x" * (50 * 1024 * 1024 + 1)
        with pytest.raises(VaultWriteFailed, match="too large"):
            store_evidence(vault_dir, "f-1", big)

    def test_wrong_key_fails_decrypt(self, vault_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        data = b"secret evidence"
        store_evidence(vault_dir, "f-1", data)
        # Change key for retrieval.
        monkeypatch.setenv("PGO_VAULT_KEY", "different-key")
        with pytest.raises(VaultWriteFailed, match="Decryption failed"):
            retrieve_evidence(vault_dir, "f-1")

    def test_missing_file(self, vault_dir: Path) -> None:
        with pytest.raises(FileNotFoundError):
            retrieve_evidence(vault_dir, "nonexistent")

    def test_integrity_mismatch(self, vault_dir: Path) -> None:
        store_evidence(vault_dir, "f-1", b"data")
        with pytest.raises(VaultWriteFailed, match="Integrity check"):
            retrieve_evidence(vault_dir, "f-1", expected_hash="bad_hash")


# ── Permissions ────────────────────────────────────────────
class TestPermissions:
    def test_stored_file_owner_only(self, vault_dir: Path) -> None:
        store_evidence(vault_dir, "f-perms", b"data")
        path = vault_dir / "f-perms" / "evidence.bin"
        mode = path.stat().st_mode
        # Owner read+write only.
        assert mode & stat.S_IRUSR
        assert mode & stat.S_IWUSR
        # No group or other access.
        assert not (mode & stat.S_IRGRP)
        assert not (mode & stat.S_IWGRP)
        assert not (mode & stat.S_IROTH)
        assert not (mode & stat.S_IWOTH)

    def test_harden_directory(self, tmp_path: Path) -> None:
        d = tmp_path / "secure"
        d.mkdir()
        harden_directory_permissions(d)
        mode = d.stat().st_mode
        assert mode & stat.S_IRWXU  # Owner has full access.
        assert not (mode & stat.S_IRWXG)  # No group access.
        assert not (mode & stat.S_IRWXO)  # No other access.
