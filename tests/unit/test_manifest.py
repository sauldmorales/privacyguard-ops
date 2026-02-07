"""Tests for pgo.manifest — broker manifest loader."""

from __future__ import annotations

from pathlib import Path

import pytest

from pgo.core.errors import ManifestInvalid, ManifestNotFound, ManifestTooLarge
from pgo.manifest import BrokerTarget, load_brokers_manifest


# ── Happy path ──────────────────────────────────────────────
def test_load_valid_manifest(tmp_path: Path) -> None:
    p = tmp_path / "m.yaml"
    p.write_text(
        "brokers:\n  - name: Acme\n    domain: acme.com\n",
        encoding="utf-8",
    )
    result = load_brokers_manifest(p)
    assert len(result) == 1
    assert result[0].name == "Acme"
    assert result[0].domain == "acme.com"


def test_load_bare_list(tmp_path: Path) -> None:
    """Bare YAML list (no 'brokers' key) is accepted."""
    p = tmp_path / "m.yaml"
    p.write_text("- name: Foo\n", encoding="utf-8")
    result = load_brokers_manifest(p)
    assert len(result) == 1


def test_load_empty_yaml(tmp_path: Path) -> None:
    p = tmp_path / "m.yaml"
    p.write_text("", encoding="utf-8")
    assert load_brokers_manifest(p) == []


# ── Error cases ─────────────────────────────────────────────
def test_file_not_found(tmp_path: Path) -> None:
    with pytest.raises(ManifestNotFound):
        load_brokers_manifest(tmp_path / "nope.yaml")


def test_size_limit(tmp_path: Path) -> None:
    p = tmp_path / "big.yaml"
    p.write_text("x" * 2000, encoding="utf-8")
    with pytest.raises(ManifestTooLarge):
        load_brokers_manifest(p, max_size_bytes=1024)


def test_invalid_yaml(tmp_path: Path) -> None:
    p = tmp_path / "bad.yaml"
    p.write_text("{{{{not yaml", encoding="utf-8")
    with pytest.raises(ManifestInvalid, match="YAML parse error"):
        load_brokers_manifest(p)


def test_schema_violation_extra_field(tmp_path: Path) -> None:
    """extra=forbid rejects unknown keys."""
    p = tmp_path / "m.yaml"
    p.write_text("- name: X\n  unknown_field: bad\n", encoding="utf-8")
    with pytest.raises(ManifestInvalid):
        load_brokers_manifest(p)


def test_blank_name_rejected(tmp_path: Path) -> None:
    p = tmp_path / "m.yaml"
    p.write_text("- name: '  '\n", encoding="utf-8")
    with pytest.raises(ManifestInvalid):
        load_brokers_manifest(p)


# ── Legacy compatibility ────────────────────────────────────
def test_legacy_broker_key_mapped_to_name(tmp_path: Path) -> None:
    """Old manifests with 'broker' instead of 'name' still work."""
    p = tmp_path / "m.yaml"
    p.write_text("- broker: OldBroker\n", encoding="utf-8")
    result = load_brokers_manifest(p)
    assert result[0].name == "OldBroker"


# ── Model immutability ─────────────────────────────────────
def test_broker_target_is_frozen() -> None:
    b = BrokerTarget(name="Test")
    with pytest.raises(Exception):  # ValidationError for frozen model
        b.name = "Modified"  # type: ignore[misc]
