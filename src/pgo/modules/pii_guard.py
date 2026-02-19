"""PII guard — redaction + hashing helpers (Zero Trust boundary).

Ensures no clear-text PII leaks into logs, exports, or audit entries.

Strategies:
- Regex-based redaction of common PII patterns (emails, phones, SSNs)
- SHA-256 tokenisation of identifiers before storage
- Validation that exports contain no unguarded PII

This module is the **inner trust boundary**: every free-text field
passes through here before touching SQLite or exports.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re

# ── PII regex patterns ──────────────────────────────────────
# Ordered: most specific first to avoid partial matches.
_PII_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    # SSN (US): 123-45-6789 or 123456789
    ("SSN", re.compile(r"\b\d{3}[-]?\d{2}[-]?\d{4}\b")),
    # Email addresses
    ("EMAIL", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)),
    # US phone numbers: (555) 123-4567, 555-123-4567, 5551234567, +1-555-123-4567
    ("PHONE", re.compile(
        r"(?:\+?1[-.\s]?)?"           # optional country code
        r"(?:\(?\d{3}\)?[-.\s]?)"     # area code
        r"\d{3}[-.\s]?\d{4}\b"
    )),
    # Credit card (basic: 13-19 digit sequences with optional separators)
    ("CC", re.compile(r"\b(?:\d[-\s]?){13,19}\b")),
]

# Characters allowed in finding_id / broker_name (whitelist approach).
_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_\-. ]{1,128}$")

# URL whitelist: only http/https
_SAFE_URL_RE = re.compile(r"^https?://[^\s]{1,2048}$")


def redact_pii(text: str) -> str:
    """Replace all detected PII patterns with ``[REDACTED-<TYPE>]``.

    This is a *best-effort* defence-in-depth measure, not a guarantee.
    The goal is to catch common accidental PII before it hits storage.

    Parameters
    ----------
    text:
        Any free-text string (notes, descriptions, etc.).

    Returns
    -------
    str
        Text with PII patterns replaced.
    """
    result = text
    for label, pattern in _PII_PATTERNS:
        result = pattern.sub(f"[REDACTED-{label}]", result)
    return result


def contains_pii(text: str) -> bool:
    """Check if text contains any detectable PII patterns.

    Returns
    -------
    bool
        True if any PII pattern matches.
    """
    return any(pattern.search(text) for _, pattern in _PII_PATTERNS)


def tokenise(value: str, *, key: str = "") -> str:
    """Return a one-way HMAC-SHA256 token of *value*.

    Uses HMAC (keyed hash) instead of plain SHA-256 to defend against
    dictionary and rainbow-table attacks on low-entropy inputs like
    phone numbers or email addresses.

    If *key* is not provided, the function reads ``PGO_TOKEN_KEY`` from
    the environment (falling back to ``PGO_VAULT_KEY``).  If neither is
    set, a ``ValueError`` is raised — tokenisation without a secret key
    offers no protection against offline attacks.

    Parameters
    ----------
    value:
        The string to tokenise (e.g. an email, a name).
    key:
        Explicit HMAC key.  If empty, the environment is consulted.

    Returns
    -------
    str
        Hex-encoded HMAC-SHA256 digest.

    Raises
    ------
    ValueError
        If no HMAC key is available (neither argument nor environment).
    """
    if not key:
        key = os.environ.get("PGO_TOKEN_KEY", "") or os.environ.get("PGO_VAULT_KEY", "")
    if not key:
        raise ValueError(
            "Tokenisation requires a secret key. "
            "Set PGO_TOKEN_KEY or PGO_VAULT_KEY environment variable."
        )
    return hmac.new(
        key.encode("utf-8"),
        value.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def validate_finding_id(finding_id: str) -> str:
    """Validate and sanitise a finding ID.

    Raises
    ------
    ValueError
        If the ID contains disallowed characters or is too long.
    """
    finding_id = finding_id.strip()
    if not finding_id:
        raise ValueError("finding_id must not be empty")
    if not _SAFE_ID_RE.match(finding_id):
        raise ValueError(
            f"finding_id contains invalid characters or is too long (max 128): {finding_id!r}"
        )
    return finding_id


def validate_broker_name(name: str) -> str:
    """Validate and sanitise a broker name.

    Raises
    ------
    ValueError
        If the name contains disallowed characters or is too long.
    """
    name = name.strip()
    if not name:
        raise ValueError("broker_name must not be empty")
    if not _SAFE_ID_RE.match(name):
        raise ValueError(
            f"broker_name contains invalid characters or is too long (max 128): {name!r}"
        )
    return name


def validate_url(url: str | None) -> str | None:
    """Validate a URL (only http/https allowed).

    Returns
    -------
    str | None
        The validated URL or None.

    Raises
    ------
    ValueError
        If the URL is not a valid http/https URL.
    """
    if url is None:
        return None
    url = url.strip()
    if not url:
        return None
    if not _SAFE_URL_RE.match(url):
        raise ValueError(f"URL must be http/https and under 2048 chars: {url!r}")
    return url


def sanitise_notes(notes: str) -> str:
    """Sanitise free-text notes: redact PII, limit length.

    Parameters
    ----------
    notes:
        Raw user-provided notes string.

    Returns
    -------
    str
        Sanitised notes (PII redacted, max 4096 chars).
    """
    notes = notes[:4096]  # Hard limit to prevent abuse.
    notes = redact_pii(notes)
    return notes
