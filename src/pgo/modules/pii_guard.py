"""PII guard — redaction + hashing helpers.

Ensures no clear-text PII leaks into logs, exports, or audit entries.

Strategies:
- Regex-based redaction of common PII patterns (emails, phones, SSNs)
- SHA-256 tokenisation of identifiers before storage
- Validation that exports contain no unguarded PII

This module is used by the vault and audit export pipelines.
"""

from __future__ import annotations

__all__: list[str] = []

# TODO: implement PII regex scanner
# TODO: implement hash-based tokenisation
# TODO: implement export PII leak detection
