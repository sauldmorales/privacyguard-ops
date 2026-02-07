"""Repo root resolver.

The single source of truth for "where is the PGO project root?".
All path derivation starts here — never from ``Path.cwd()`` alone.

Algorithm
---------
Walk from *start* (default ``cwd()``) upward through parents looking for
``pyproject.toml``.  The first directory that contains it is the root.

Why this matters
----------------
If you run ``pgo status`` from ``manifests/`` or ``src/``, the CLI must
still resolve paths correctly.  Hard-coding ``Path("manifests/...")``
relative to cwd would break immediately.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pgo.core.errors import RepoRootNotFound

# Marker file that identifies the repository root.
_MARKER = "pyproject.toml"


def find_repo_root(start: Path | None = None) -> Path:
    """Return the repo root directory.

    Parameters
    ----------
    start:
        Directory to start searching from.  Defaults to ``Path.cwd()``.

    Returns
    -------
    Path
        Absolute, resolved path to the repo root.

    Raises
    ------
    RepoRootNotFound
        If no ``pyproject.toml`` is found in *start* or any of its parents.
    """
    origin = (start or Path.cwd()).resolve()
    for candidate in [origin, *origin.parents]:
        if (candidate / _MARKER).is_file():
            return candidate
    raise RepoRootNotFound(start_path=str(origin))


@lru_cache(maxsize=1)
def repo_root() -> Path:
    """Cached version of :func:`find_repo_root` (from cwd at first call)."""
    return find_repo_root()
