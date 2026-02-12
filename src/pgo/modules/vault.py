"""Evidence vault — redact / hash / encrypt local evidence.

Handles the evidence lifecycle:
1. Redact (basic PII masking)
2. Hash (SHA-256 for integrity)
3. Encrypt (local key from PGO_VAULT_KEY env var)
4. Store with timestamp + integrity hash

Non-goal: the vault does NOT auto-capture screenshots.
Users provide evidence files (BYOS), and the vault protects them.
"""

from __future__ import annotations

from pgo.core.errors import VaultKeyMissing, VaultWriteFailed

__all__ = [
    "VaultKeyMissing",
    "VaultWriteFailed",
]

# TODO: implement vault store / retrieve / encrypt / decrypt
# TODO: implement redaction pipeline before storage
