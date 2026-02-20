"""Enterprise invariant tests for vault.py — anti-regression guards.

These tests verify structural properties of the vault module source code
itself, preventing regressions to unsafe patterns.  They are NOT runtime
tests; they inspect the source text as a static invariant.

If any of these fail, it means someone reintroduced a banned pattern
(e.g. direct ``write_bytes()`` to evidence files without atomic rename).
"""

from __future__ import annotations

from pathlib import Path


_VAULT_SRC = Path("src/pgo/modules/vault.py").read_text(encoding="utf-8")


class TestVaultSourceInvariants:
    """Guard against regressions to unsafe I/O patterns."""

    def test_no_direct_write_bytes(self) -> None:
        """vault.py must NOT use Path.write_bytes() for evidence storage.

        Direct write_bytes() is non-atomic: a crash mid-write corrupts the
        target file.  Evidence must be written via temp → fsync → os.replace.
        """
        # .write_bytes( appears in retrieve? No — only read_bytes is used there.
        # We ban write_bytes entirely in the module to prevent misuse.
        assert ".write_bytes(" not in _VAULT_SRC, (
            "REGRESSION: vault.py contains .write_bytes() — "
            "evidence must use atomic write (temp → fsync → os.replace)"
        )

    def test_uses_atomic_rename(self) -> None:
        """vault.py must use os.replace() for atomic rename."""
        assert "os.replace" in _VAULT_SRC, (
            "REGRESSION: vault.py missing os.replace() — "
            "atomic rename is required for evidence integrity"
        )

    def test_uses_tempfile(self) -> None:
        """vault.py must create temp files via tempfile.mkstemp()."""
        assert "mkstemp" in _VAULT_SRC, (
            "REGRESSION: vault.py missing tempfile.mkstemp() — "
            "temp file in same directory is required for atomic write"
        )

    def test_uses_fsync(self) -> None:
        """vault.py must fsync before rename for durability."""
        assert "os.fsync" in _VAULT_SRC, (
            "REGRESSION: vault.py missing os.fsync() — "
            "fsync is required before atomic rename for crash safety"
        )

    def test_uses_directory_fsync(self) -> None:
        """vault.py must fsync the directory after rename for full durability."""
        # The directory fsync pattern: os.open(..., O_RDONLY) + os.fsync(dir_fd)
        assert "O_RDONLY" in _VAULT_SRC, (
            "REGRESSION: vault.py missing directory fsync — "
            "directory must be fsync'd after os.replace for power-loss durability"
        )

    def test_enforces_size_limit(self) -> None:
        """vault.py must enforce _MAX_EVIDENCE_BYTES."""
        assert "_MAX_EVIDENCE_BYTES" in _VAULT_SRC, (
            "REGRESSION: vault.py missing size limit — "
            "CWE-400 defence requires an explicit max evidence size"
        )

    def test_uses_safe_vault_path(self) -> None:
        """vault.py must use _safe_vault_path for path traversal defence."""
        assert "_safe_vault_path" in _VAULT_SRC, (
            "REGRESSION: vault.py missing path traversal guard — "
            "_safe_vault_path is required to anchor all vault paths"
        )
