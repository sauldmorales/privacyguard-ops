"""Tests for pgo.modules.pii_guard — PII redaction + input validation.

Zero Trust boundary tests:
1. PII patterns are detected and redacted correctly.
2. Input validation rejects malicious / invalid inputs.
3. Notes are sanitised (PII removed, length capped).
4. Tokenisation is one-way and deterministic.
"""

from __future__ import annotations

import pytest

from pgo.modules.pii_guard import (
    contains_pii,
    redact_pii,
    sanitise_notes,
    tokenise,
    validate_broker_name,
    validate_finding_id,
    validate_url,
)


# ── PII detection ──────────────────────────────────────────
class TestContainsPii:
    def test_detects_email(self) -> None:
        assert contains_pii("contact me at john@example.com")

    def test_detects_ssn_dashes(self) -> None:
        assert contains_pii("SSN: 123-45-6789")

    def test_detects_ssn_no_dashes(self) -> None:
        assert contains_pii("SSN: 123456789")

    def test_detects_phone(self) -> None:
        assert contains_pii("Call (555) 123-4567")

    def test_detects_credit_card(self) -> None:
        assert contains_pii("Card: 4111-1111-1111-1111")

    def test_clean_text(self) -> None:
        assert not contains_pii("This is perfectly clean text without PII")

    def test_empty_string(self) -> None:
        assert not contains_pii("")


# ── PII redaction ──────────────────────────────────────────
class TestRedactPii:
    def test_redacts_email(self) -> None:
        result = redact_pii("Email: john@example.com end")
        assert "john@example.com" not in result
        assert "[REDACTED-EMAIL]" in result

    def test_redacts_phone(self) -> None:
        result = redact_pii("Phone: (555) 123-4567 done")
        assert "[REDACTED-PHONE]" in result

    def test_redacts_ssn(self) -> None:
        result = redact_pii("SSN is 123-45-6789 here")
        assert "[REDACTED-SSN]" in result

    def test_redacts_multiple(self) -> None:
        result = redact_pii("john@test.com called (555) 123-4567")
        assert "[REDACTED-EMAIL]" in result
        assert "[REDACTED-PHONE]" in result

    def test_preserves_clean_text(self) -> None:
        text = "This broker has no PII in this note"
        assert redact_pii(text) == text


# ── Tokenisation ───────────────────────────────────────────
class TestTokenise:
    def test_deterministic(self) -> None:
        assert tokenise("hello") == tokenise("hello")

    def test_different_inputs(self) -> None:
        assert tokenise("hello") != tokenise("world")

    def test_salt_changes_output(self) -> None:
        assert tokenise("hello", salt="a") != tokenise("hello", salt="b")

    def test_returns_hex_string(self) -> None:
        result = tokenise("test")
        assert len(result) == 64  # SHA-256 hex digest
        assert all(c in "0123456789abcdef" for c in result)


# ── validate_finding_id ────────────────────────────────────
class TestValidateFindingId:
    def test_valid_simple(self) -> None:
        assert validate_finding_id("f-1") == "f-1"

    def test_valid_with_dots(self) -> None:
        assert validate_finding_id("broker.profile.001") == "broker.profile.001"

    def test_strips_whitespace(self) -> None:
        assert validate_finding_id("  f-1  ") == "f-1"

    def test_rejects_empty(self) -> None:
        with pytest.raises(ValueError, match="must not be empty"):
            validate_finding_id("")

    def test_rejects_sql_injection(self) -> None:
        with pytest.raises(ValueError, match="invalid characters"):
            validate_finding_id("'; DROP TABLE findings;--")

    def test_rejects_path_traversal(self) -> None:
        with pytest.raises(ValueError, match="invalid characters"):
            validate_finding_id("../../etc/passwd")

    def test_rejects_too_long(self) -> None:
        with pytest.raises(ValueError, match="invalid characters"):
            validate_finding_id("a" * 129)

    def test_accepts_max_length(self) -> None:
        assert len(validate_finding_id("a" * 128)) == 128


# ── validate_broker_name ───────────────────────────────────
class TestValidateBrokerName:
    def test_valid(self) -> None:
        assert validate_broker_name("BeenVerified") == "BeenVerified"

    def test_valid_with_spaces(self) -> None:
        assert validate_broker_name("White Pages") == "White Pages"

    def test_rejects_empty(self) -> None:
        with pytest.raises(ValueError, match="must not be empty"):
            validate_broker_name("")

    def test_rejects_special_chars(self) -> None:
        with pytest.raises(ValueError, match="invalid characters"):
            validate_broker_name("broker<script>alert(1)</script>")


# ── validate_url ───────────────────────────────────────────
class TestValidateUrl:
    def test_valid_https(self) -> None:
        assert validate_url("https://example.com/remove") == "https://example.com/remove"

    def test_valid_http(self) -> None:
        assert validate_url("http://example.com") == "http://example.com"

    def test_none_returns_none(self) -> None:
        assert validate_url(None) is None

    def test_empty_returns_none(self) -> None:
        assert validate_url("") is None

    def test_rejects_javascript(self) -> None:
        with pytest.raises(ValueError, match="http/https"):
            validate_url("javascript:alert(1)")

    def test_rejects_file(self) -> None:
        with pytest.raises(ValueError, match="http/https"):
            validate_url("file:///etc/passwd")

    def test_rejects_ftp(self) -> None:
        with pytest.raises(ValueError, match="http/https"):
            validate_url("ftp://evil.com/payload")

    def test_rejects_too_long(self) -> None:
        with pytest.raises(ValueError, match="2048"):
            validate_url("https://example.com/" + "a" * 2050)


# ── sanitise_notes ─────────────────────────────────────────
class TestSanitiseNotes:
    def test_redacts_pii(self) -> None:
        result = sanitise_notes("Called john@evil.com about removal")
        assert "john@evil.com" not in result
        assert "[REDACTED-EMAIL]" in result

    def test_caps_length(self) -> None:
        result = sanitise_notes("x" * 5000)
        assert len(result) <= 4096

    def test_preserves_clean_notes(self) -> None:
        assert sanitise_notes("Submitted opt-out form today") == "Submitted opt-out form today"
