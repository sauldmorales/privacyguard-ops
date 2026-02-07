"""Tests for pgo.core.settings — runtime settings resolution."""

from __future__ import annotations

from pathlib import Path

from pgo.core.settings import Settings


def test_settings_auto_resolves_paths(tmp_path: Path) -> None:
    """Given an explicit repo_root, all sub-dirs derive from it."""
    (tmp_path / "pyproject.toml").touch()
    s = Settings(repo_root=tmp_path)

    assert s.repo_root == tmp_path
    assert s.manifests_dir == tmp_path / "manifests"
    assert s.vault_dir == tmp_path / "vault"
    assert s.data_dir == tmp_path / "data"
    assert s.reports_dir == tmp_path / "reports"
    assert s.exports_dir == tmp_path / "exports"


def test_settings_manifest_path(tmp_path: Path) -> None:
    """manifest_path combines manifests_dir + filename."""
    s = Settings(repo_root=tmp_path)
    assert s.manifest_path == tmp_path / "manifests" / "brokers_manifest.yaml"


def test_settings_ensure_dirs_creates_directories(tmp_path: Path) -> None:
    """ensure_dirs() must create vault/, data/, reports/, exports/."""
    s = Settings(repo_root=tmp_path)
    s.ensure_dirs()

    assert s.vault_dir is not None and s.vault_dir.is_dir()
    assert s.data_dir is not None and s.data_dir.is_dir()
    assert s.reports_dir is not None and s.reports_dir.is_dir()
    assert s.exports_dir is not None and s.exports_dir.is_dir()


def test_settings_override_individual_dir(tmp_path: Path) -> None:
    """Explicit vault_dir overrides the default derivation."""
    custom_vault = tmp_path / "my_vault"
    s = Settings(repo_root=tmp_path, vault_dir=custom_vault)
    assert s.vault_dir == custom_vault


def test_settings_defaults_log(tmp_path: Path) -> None:
    """Default logging settings."""
    s = Settings(repo_root=tmp_path)
    assert s.log_level == "INFO"
    assert s.log_json is True
