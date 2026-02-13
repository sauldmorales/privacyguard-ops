"""Tests for HMAC signature + audit notes sanitisation (Zero Trust)."""

from __future__ import annotations

import os

import pytest

from pgo.core.audit import compute_hmac


class TestComputeHmac:
    def test_returns_none_without_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("PGO_VAULT_KEY", raising=False)
        assert compute_hmac("test data") is None

    def test_returns_hex_with_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PGO_VAULT_KEY", "secret")
        sig = compute_hmac("test data")
        assert sig is not None
        assert len(sig) == 64
        assert all(c in "0123456789abcdef" for c in sig)

    def test_deterministic(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PGO_VAULT_KEY", "secret")
        assert compute_hmac("data") == compute_hmac("data")

    def test_different_data_different_sig(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PGO_VAULT_KEY", "secret")
        assert compute_hmac("data1") != compute_hmac("data2")

    def test_different_key_different_sig(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PGO_VAULT_KEY", "key1")
        sig1 = compute_hmac("data")
        monkeypatch.setenv("PGO_VAULT_KEY", "key2")
        sig2 = compute_hmac("data")
        assert sig1 != sig2
