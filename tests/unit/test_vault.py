"""Tests for pgo.modules.vault — evidence encryption/decryption.

Zero Trust tests:
1. Store + retrieve round-trip with integrity check.
2. Wrong key fails decryption.
3. Missing key raises VaultKeyMissing.
4. Oversized evidence is rejected.
5. Empty evidence is rejected.
6. File permissions are restricted.
7. AES-256-GCM produces authenticated ciphertext (not Fernet).
8. PBKDF2 key derivation: same passphrase + different salt = different key.
9. Path traversal: finding_id with ".." is blocked at execution point.
"""

from __future__ import annotations

import stat
from pathlib import Path

import pytest

from pgo.core.errors import VaultKeyMissing, VaultPathTraversal, VaultWriteFailed

# Skip all tests if cryptography is not installed.
cryptography = pytest.importorskip("cryptography")

from pgo.modules.vault import (  # noqa: E402
    _HEADER_BYTES,
    _derive_key,
    _safe_vault_path,
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


# ── AES-256-GCM specific tests ─────────────────────────────
class TestAES256GCM:
    def test_ciphertext_is_not_fernet(self, vault_dir: Path) -> None:
        """Verify output is AES-256-GCM wire format, not Fernet."""
        data = b"evidence bytes"
        store_evidence(vault_dir, "f-gcm", data)
        raw = (vault_dir / "f-gcm" / "evidence.bin").read_bytes()
        # Fernet tokens start with 0x80 version byte; GCM does not have that prefix.
        # Our wire format: salt(16) + nonce(12) + ciphertext+tag
        assert len(raw) > _HEADER_BYTES
        # Fernet tokens are base64-encoded; our format is raw binary.
        # If it were Fernet, decoding as ASCII would succeed (base64 is ASCII).
        with pytest.raises(UnicodeDecodeError):
            raw.decode("ascii")

    def test_different_encryptions_produce_different_ciphertext(self, vault_dir: Path) -> None:
        """Each encryption uses a random salt + nonce, so ciphertext differs."""
        data = b"same data"
        store_evidence(vault_dir, "f-r1", data)
        store_evidence(vault_dir, "f-r2", data)
        ct1 = (vault_dir / "f-r1" / "evidence.bin").read_bytes()
        ct2 = (vault_dir / "f-r2" / "evidence.bin").read_bytes()
        assert ct1 != ct2  # Different salt+nonce = different ciphertext.


# ── PBKDF2 key derivation tests ────────────────────────────
class TestKeyDerivation:
    def test_same_passphrase_same_salt_same_key(self) -> None:
        salt = b"\x00" * 16
        k1 = _derive_key("passphrase", salt)
        k2 = _derive_key("passphrase", salt)
        assert k1 == k2
        assert len(k1) == 32  # AES-256

    def test_same_passphrase_different_salt_different_key(self) -> None:
        k1 = _derive_key("passphrase", b"\x00" * 16)
        k2 = _derive_key("passphrase", b"\x01" * 16)
        assert k1 != k2

    def test_different_passphrase_same_salt_different_key(self) -> None:
        salt = b"\x00" * 16
        k1 = _derive_key("pass1", salt)
        k2 = _derive_key("pass2", salt)
        assert k1 != k2


# ── Path traversal defence tests ───────────────────────────
class TestPathTraversal:
    def test_blocks_dotdot_in_finding_id(self, vault_dir: Path) -> None:
        """finding_id='../../etc/passwd' must be blocked at execution point."""
        with pytest.raises(VaultPathTraversal):
            _safe_vault_path(vault_dir, "../../etc", "passwd")

    def test_blocks_dotdot_in_filename(self, vault_dir: Path) -> None:
        with pytest.raises(VaultPathTraversal):
            _safe_vault_path(vault_dir, "legit-id", "../../etc/passwd")

    def test_blocks_absolute_path_component(self, vault_dir: Path) -> None:
        with pytest.raises(VaultPathTraversal):
            _safe_vault_path(vault_dir, "/etc/passwd")

    def test_allows_normal_finding_id(self, vault_dir: Path) -> None:
        path = _safe_vault_path(vault_dir, "finding-123", "evidence.bin")
        assert path.is_relative_to(vault_dir.resolve())

    def test_store_rejects_traversal_finding_id(self, vault_dir: Path) -> None:
        """End-to-end: store_evidence blocks path traversal."""
        with pytest.raises(VaultPathTraversal):
            store_evidence(vault_dir, "../../../tmp/evil", b"data")

    def test_retrieve_rejects_traversal_finding_id(self, vault_dir: Path) -> None:
        with pytest.raises(VaultPathTraversal):
            retrieve_evidence(vault_dir, "../../../etc/passwd")
