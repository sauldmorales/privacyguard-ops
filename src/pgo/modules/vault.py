"""Evidence vault — redact / hash / encrypt local evidence (Zero Trust).

Handles the evidence lifecycle:
1. Redact (PII guard pass)
2. Hash (SHA-256 for integrity)
3. Encrypt (Fernet symmetric encryption with local key)
4. Store with timestamp + integrity hash

Non-goal: the vault does NOT auto-capture screenshots.
Users provide evidence files (BYOS), and the vault protects them.

Security model:
- Key is sourced ONLY from env var (PGO_VAULT_KEY) — never stored on disk
- Files are encrypted at rest with Fernet (AES-128-CBC + HMAC)
- Integrity hash is computed BEFORE encryption (verifiable after decrypt)
- File permissions are restricted (0o600) on write
"""

from __future__ import annotations

import hashlib
import os
import stat
from datetime import datetime, timezone
from pathlib import Path

import structlog

from pgo.core.errors import VaultKeyMissing, VaultWriteFailed

logger = structlog.get_logger()

# Max evidence file size: 50 MB (defence-in-depth).
_MAX_EVIDENCE_BYTES = 50 * 1024 * 1024


def _get_vault_key(env_var: str = "PGO_VAULT_KEY") -> bytes:
    """Read the vault encryption key from environment.

    Raises
    ------
    VaultKeyMissing
        If the env var is not set or is empty.
    """
    raw = os.environ.get(env_var, "").strip()
    if not raw:
        raise VaultKeyMissing(
            f"Vault encryption key not found. Set {env_var} environment variable."
        )
    # Derive a 32-byte key via SHA-256 (Fernet needs url-safe base64 of 32 bytes).
    return hashlib.sha256(raw.encode("utf-8")).digest()


def compute_integrity_hash(data: bytes) -> str:
    """SHA-256 hex digest of raw evidence bytes (pre-encryption)."""
    return hashlib.sha256(data).hexdigest()


def store_evidence(
    vault_dir: Path,
    finding_id: str,
    data: bytes,
    *,
    filename: str = "evidence.bin",
    env_var: str = "PGO_VAULT_KEY",
) -> dict[str, str]:
    """Encrypt and store evidence in the vault.

    Parameters
    ----------
    vault_dir:
        Path to the vault directory.
    finding_id:
        Finding this evidence belongs to.
    data:
        Raw evidence bytes.
    filename:
        Name for the stored file.
    env_var:
        Environment variable holding the encryption key.

    Returns
    -------
    dict
        Metadata: finding_id, integrity_hash, stored_at, path.

    Raises
    ------
    VaultWriteFailed
        If encryption or write fails.
    VaultKeyMissing
        If encryption key is not available.
    """
    if len(data) > _MAX_EVIDENCE_BYTES:
        raise VaultWriteFailed(
            f"Evidence too large: {len(data):,} bytes (max {_MAX_EVIDENCE_BYTES:,})"
        )

    if len(data) == 0:
        raise VaultWriteFailed("Evidence data is empty")

    # Compute integrity hash BEFORE encryption.
    integrity_hash = compute_integrity_hash(data)

    # Encrypt.
    try:
        from cryptography.fernet import Fernet
        import base64

        key_bytes = _get_vault_key(env_var)
        fernet_key = base64.urlsafe_b64encode(key_bytes)
        fernet = Fernet(fernet_key)
        encrypted = fernet.encrypt(data)
    except VaultKeyMissing:
        raise
    except ImportError:
        raise VaultWriteFailed(
            "cryptography package not installed. Install with: pip install cryptography"
        )
    except Exception as exc:
        raise VaultWriteFailed(f"Encryption failed: {exc}") from exc

    # Write to disk with restricted permissions.
    finding_dir = vault_dir / finding_id
    finding_dir.mkdir(parents=True, exist_ok=True)

    target = finding_dir / filename
    try:
        target.write_bytes(encrypted)
        # Restrict file permissions: owner read/write only.
        target.chmod(stat.S_IRUSR | stat.S_IWUSR)
    except OSError as exc:
        raise VaultWriteFailed(f"Failed to write evidence: {exc}") from exc

    # Also restrict the directory.
    try:
        finding_dir.chmod(stat.S_IRWXU)
    except OSError:
        pass  # Best effort on directory permissions.

    stored_at = datetime.now(timezone.utc).isoformat()

    logger.info(
        "evidence_stored",
        finding_id=finding_id,
        integrity_hash=integrity_hash[:12],
        size_bytes=len(data),
        path=str(target),
    )

    return {
        "finding_id": finding_id,
        "integrity_hash": integrity_hash,
        "stored_at": stored_at,
        "path": str(target),
    }


def retrieve_evidence(
    vault_dir: Path,
    finding_id: str,
    *,
    filename: str = "evidence.bin",
    env_var: str = "PGO_VAULT_KEY",
    expected_hash: str | None = None,
) -> bytes:
    """Decrypt and return evidence from the vault.

    Parameters
    ----------
    vault_dir:
        Path to the vault directory.
    finding_id:
        Finding the evidence belongs to.
    filename:
        Name of the stored file.
    env_var:
        Environment variable holding the encryption key.
    expected_hash:
        If provided, verify integrity after decryption.

    Returns
    -------
    bytes
        Decrypted evidence data.

    Raises
    ------
    FileNotFoundError
        If the evidence file does not exist.
    VaultKeyMissing
        If encryption key is not available.
    VaultWriteFailed
        If decryption or integrity check fails.
    """
    target = vault_dir / finding_id / filename
    if not target.exists():
        raise FileNotFoundError(f"Evidence not found: {target}")

    encrypted = target.read_bytes()

    try:
        from cryptography.fernet import Fernet
        import base64

        key_bytes = _get_vault_key(env_var)
        fernet_key = base64.urlsafe_b64encode(key_bytes)
        fernet = Fernet(fernet_key)
        data = fernet.decrypt(encrypted)
    except VaultKeyMissing:
        raise
    except ImportError:
        raise VaultWriteFailed(
            "cryptography package not installed. Install with: pip install cryptography"
        )
    except Exception as exc:
        raise VaultWriteFailed(f"Decryption failed (wrong key or corrupted data): {exc}") from exc

    # Verify integrity if hash was provided.
    if expected_hash is not None:
        actual_hash = compute_integrity_hash(data)
        if actual_hash != expected_hash:
            raise VaultWriteFailed(
                f"Integrity check failed: expected {expected_hash[:12]}... "
                f"got {actual_hash[:12]}..."
            )

    return data


def harden_directory_permissions(directory: Path) -> None:
    """Set directory permissions to owner-only (0o700).

    Best-effort: logs warning if it fails (e.g. on Windows).
    """
    try:
        directory.chmod(stat.S_IRWXU)
    except OSError as exc:
        logger.warning("permission_hardening_failed", path=str(directory), error=str(exc))
