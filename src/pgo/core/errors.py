"""PGO domain exceptions.

Every module raises typed exceptions so callers can handle failures
explicitly instead of catching bare ValueError/RuntimeError.
"""

from __future__ import annotations


# ── Base ────────────────────────────────────────────────────
class PGOError(Exception):
    """Root exception for all PGO errors."""


# ── Repo / filesystem ──────────────────────────────────────
class RepoRootNotFound(PGOError):
    """Could not locate the repository root (pyproject.toml marker)."""

    def __init__(self, start_path: str | None = None) -> None:
        where = f" (searched from {start_path})" if start_path else ""
        super().__init__(f"Repository root not found{where}: no pyproject.toml in parent chain")
        self.start_path = start_path


class DirectoryNotFound(PGOError):
    """An expected directory (vault/, data/, etc.) does not exist."""


# ── Manifest ────────────────────────────────────────────────
class ManifestNotFound(PGOError):
    """The manifest YAML file does not exist at the expected path."""


class ManifestInvalid(PGOError):
    """The manifest failed schema validation or safe-load."""


class ManifestTooLarge(ManifestInvalid):
    """The manifest file exceeds the allowed size limit."""


# ── State machine ───────────────────────────────────────────
class StateTransitionInvalid(PGOError):
    """An illegal state transition was attempted."""

    def __init__(self, from_status: str, to_status: str) -> None:
        super().__init__(f"Invalid transition: {from_status} → {to_status}")
        self.from_status = from_status
        self.to_status = to_status


# ── Audit / chain ──────────────────────────────────────────
class AuditChainBroken(PGOError):
    """Hash-chain integrity verification failed."""


# ── Vault ──────────────────────────────────────────────────
class VaultWriteFailed(PGOError):
    """Evidence could not be written to the vault."""


class VaultKeyMissing(PGOError):
    """Encryption key is not configured or not accessible."""
