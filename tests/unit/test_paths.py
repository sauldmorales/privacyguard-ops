"""Tests for pgo.core.paths — repo root resolution."""

from __future__ import annotations

from pathlib import Path

import pytest

from pgo.core.errors import RepoRootNotFound
from pgo.core.paths import find_repo_root


def test_find_repo_root_from_root(tmp_path: Path) -> None:
    """When cwd IS the root, return it."""
    (tmp_path / "pyproject.toml").touch()
    assert find_repo_root(start=tmp_path) == tmp_path


def test_find_repo_root_from_subdirectory(tmp_path: Path) -> None:
    """Walking up from a deep subdirectory must find the marker."""
    (tmp_path / "pyproject.toml").touch()
    deep = tmp_path / "src" / "pgo" / "core"
    deep.mkdir(parents=True)
    assert find_repo_root(start=deep) == tmp_path


def test_find_repo_root_from_manifests(tmp_path: Path) -> None:
    """Simulates running `pgo` from the manifests/ subdirectory."""
    (tmp_path / "pyproject.toml").touch()
    manifests = tmp_path / "manifests"
    manifests.mkdir()
    assert find_repo_root(start=manifests) == tmp_path


def test_find_repo_root_raises_when_missing(tmp_path: Path) -> None:
    """No pyproject.toml anywhere → RepoRootNotFound."""
    isolated = tmp_path / "no_marker_here"
    isolated.mkdir()
    with pytest.raises(RepoRootNotFound):
        find_repo_root(start=isolated)


def test_find_repo_root_resolved_is_absolute(tmp_path: Path) -> None:
    """Result is always an absolute, resolved path."""
    (tmp_path / "pyproject.toml").touch()
    result = find_repo_root(start=tmp_path)
    assert result.is_absolute()
    assert result == result.resolve()
