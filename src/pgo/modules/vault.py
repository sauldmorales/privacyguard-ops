"""Evidence vault — redact / hash / encrypt local evidence (Zero Trust).

Handles the evidence lifecycle:
1. Redact (PII guard pass)
2. Hash (SHA-256 for integrity)
3. Encrypt (AES-256-GCM authenticated encryption with derived key)
4. Store with timestamp + integrity hash

Non-goal: the vault does NOT auto-capture screenshots.
Users provide evidence files (BYOS), and the vault protects them.

Security model:
- Key is sourced ONLY from env var (PGO_VAULT_KEY) — never stored on disk
- Key derivation: PBKDF2-HMAC-SHA256 (600_000 iterations) with per-file random salt
- Encryption: AES-256-GCM (AEAD — native authenticated encryption)
- Integrity hash is computed BEFORE encryption (verifiable after decrypt)
- File permissions are restricted (0o600) on write
- Path anchoring: all vault paths are resolved and verified against vault root

Cryptographic rationale (vs previous Fernet/AES-128-CBC):
- AES-256-GCM provides native AEAD (no separate HMAC needed, smaller attack surface)
- AES-256 meets FIPS 140-3 / Suite B requirements (Fernet's AES-128 does not)
- PBKDF2 with high iteration count defends against brute-force on user passphrases
  (previous implementation used single-pass SHA-256, which is NOT a KDF)
- Per-file random salt prevents key reuse across evidence files

Atomic write strategy (CWE-362 defence):
- Evidence is written to a temporary file in the same directory as the target.
- After write + fsync, ``os.replace()`` atomically renames temp → target.
- Directory is fsync'd after rename for full durability (ext4/Linux power-loss).
- On crash/interrupt the target is either the old file or absent — never corrupt.

Design constraint — evidence size limit (CWE-400 / OOM defence):
- ``store_evidence()`` rejects inputs larger than ``_MAX_EVIDENCE_BYTES`` (50 MB).
- This is an *operational* guardrail, not a streaming architecture.
- The AES-256-GCM one-shot API (``AESGCM.encrypt()``) requires the full plaintext
  in memory; streaming GCM would require the low-level ``Cipher()`` API.
- If the product requires evidence files > 50 MB, migrate to v3 wire format with
  incremental ``Cipher(AES, GCM).encryptor().update(chunk)`` streaming.
"""

from __future__ import annotations

import hashlib
import os
import stat
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import structlog

from pgo.core.errors import VaultKeyMissing, VaultPathTraversal, VaultWriteFailed

logger = structlog.get_logger()

# Max evidence file size: 50 MB (defence-in-depth).
_MAX_EVIDENCE_BYTES = 50 * 1024 * 1024

# PBKDF2 parameters (NIST SP 800-132 / OWASP 2024 recommendation).
_KDF_ITERATIONS = 600_000
_SALT_BYTES = 16
_KEY_BYTES = 32  # AES-256

# AES-256-GCM nonce size (96 bits per NIST SP 800-38D recommendation).
_NONCE_BYTES = 12

# Wire format: salt (16) || nonce (12) || ciphertext+tag (variable).
_HEADER_BYTES = _SALT_BYTES + _NONCE_BYTES


def _get_vault_key_raw(env_var: str = "PGO_VAULT_KEY") -> str:
    """Read the raw vault key string from environment.

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
    return raw


def _derive_key(passphrase: str, salt: bytes) -> bytes:
    """Derive a 256-bit AES key from a passphrase using PBKDF2-HMAC-SHA256.

    Parameters
    ----------
    passphrase:
        The raw key material from PGO_VAULT_KEY.
    salt:
        A random salt (16 bytes) unique to each encryption operation.

    Returns
    -------
    bytes
        32-byte derived key suitable for AES-256.
    """
    return hashlib.pbkdf2_hmac(
        "sha256",
        passphrase.encode("utf-8"),
        salt,
        iterations=_KDF_ITERATIONS,
        dklen=_KEY_BYTES,
    )


def _encrypt_aes256gcm(data: bytes, passphrase: str) -> bytes:
    """Encrypt data using AES-256-GCM with a PBKDF2-derived key.

    Wire format: salt (16B) || nonce (12B) || ciphertext+tag (variable).

    Returns
    -------
    bytes
        The concatenated salt + nonce + ciphertext (includes GCM auth tag).
    """
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    salt = os.urandom(_SALT_BYTES)
    nonce = os.urandom(_NONCE_BYTES)
    key = _derive_key(passphrase, salt)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, data, None)
    return salt + nonce + ciphertext


def _decrypt_aes256gcm(blob: bytes, passphrase: str) -> bytes:
    """Decrypt an AES-256-GCM blob produced by ``_encrypt_aes256gcm``.

    Raises
    ------
    Exception
        If decryption fails (wrong key, corrupted data, tampered ciphertext).
    """
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    if len(blob) < _HEADER_BYTES + 16:  # 16 = minimum GCM tag
        raise ValueError("Ciphertext too short to contain valid AES-256-GCM data")

    salt = blob[:_SALT_BYTES]
    nonce = blob[_SALT_BYTES : _SALT_BYTES + _NONCE_BYTES]
    ciphertext = blob[_SALT_BYTES + _NONCE_BYTES :]

    key = _derive_key(passphrase, salt)
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ciphertext, None)


def _safe_vault_path(vault_dir: Path, *components: str) -> Path:
    """Resolve a vault path and verify it stays inside the vault root.

    This is the execution-point path traversal defence. Even if input
    validation at the boundary is bypassed, this function ensures no
    file operation escapes the vault directory.

    Parameters
    ----------
    vault_dir:
        The resolved vault root directory.
    components:
        Path components (finding_id, filename) to join.

    Returns
    -------
    Path
        The resolved, verified target path.

    Raises
    ------
    VaultPathTraversal
        If the resolved path escapes the vault root.
    """
    vault_root = vault_dir.resolve()
    target = vault_root.joinpath(*components).resolve()

    if not target.is_relative_to(vault_root):
        raise VaultPathTraversal(
            component="/".join(components),
            vault_root=str(vault_root),
        )
    return target


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

    # Encrypt with AES-256-GCM (AEAD) + PBKDF2-derived key.
    try:
        passphrase = _get_vault_key_raw(env_var)
        encrypted = _encrypt_aes256gcm(data, passphrase)
    except VaultKeyMissing:
        raise
    except ImportError:
        raise VaultWriteFailed(
            "cryptography package not installed. Install with: pip install cryptography"
        )
    except Exception as exc:
        raise VaultWriteFailed(f"Encryption failed: {exc}") from exc

    # Path anchoring: resolve + verify target stays inside vault root.
    finding_dir = _safe_vault_path(vault_dir, finding_id)
    finding_dir.mkdir(parents=True, exist_ok=True)

    target = _safe_vault_path(vault_dir, finding_id, filename)

    # --- Atomic write: temp → fsync → os.replace (CWE-362 defence) ---
    # Writing to a temp file in the SAME directory guarantees os.replace()
    # is an atomic rename on the same filesystem.  If the process dies
    # mid-write, the target file is either the old version or absent —
    # never a half-written corrupt blob.
    fd = None
    tmp_path: str | None = None
    try:
        fd, tmp_path = tempfile.mkstemp(
            dir=str(finding_dir),
            prefix=".evidence_",
            suffix=".tmp",
        )
        os.write(fd, encrypted)
        os.fsync(fd)
        os.close(fd)
        fd = None  # Prevent double-close in the except/finally block.

        # Set restrictive permissions BEFORE the atomic rename so the
        # file is never visible with default-open permissions.
        os.chmod(tmp_path, stat.S_IRUSR | stat.S_IWUSR)

        # Atomic rename (POSIX guarantees for same-filesystem rename).
        os.replace(tmp_path, str(target))
        tmp_path = None  # Rename succeeded; nothing to clean up.

        # Fsync the *directory* to ensure the rename is durable on
        # Linux/ext4.  Without this, a power loss after os.replace()
        # could leave the directory entry pointing at the old inode.
        # Best-effort: non-fatal if it fails (e.g. Windows / exotic FS).
        try:
            dir_fd = os.open(str(finding_dir), os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        except OSError:
            pass
    except OSError as exc:
        raise VaultWriteFailed(f"Failed to write evidence: {exc}") from exc
    finally:
        # Defensive cleanup: close fd if still open, remove temp if rename
        # did not happen (e.g. permission error after write).
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
        if tmp_path is not None:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

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
    # Path anchoring: resolve + verify target stays inside vault root.
    target = _safe_vault_path(vault_dir, finding_id, filename)
    if not target.exists():
        raise FileNotFoundError(f"Evidence not found: {target}")

    encrypted = target.read_bytes()

    try:
        passphrase = _get_vault_key_raw(env_var)
        data = _decrypt_aes256gcm(encrypted, passphrase)
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
