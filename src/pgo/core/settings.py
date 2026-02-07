"""PGO runtime settings (Pydantic v2 Settings).

Centralises every configurable path / flag so that:

* The CLI never hard-codes relative paths.
* Environment overrides work (``PGO_VAULT_DIR``, etc.).
* Tests can inject a custom root via ``Settings(repo_root=tmp_path)``.

Usage
-----
::

    from pgo.core.settings import get_settings

    s = get_settings()          # auto-detects root from cwd
    s.vault_dir.mkdir(...)      # always correct, regardless of cwd
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from pgo.core.paths import find_repo_root


class Settings(BaseSettings):
    """All runtime configuration for PGO.

    *repo_root* anchors every derived path.  If not supplied, it is
    auto-detected via :func:`pgo.core.paths.find_repo_root`.
    """

    model_config = SettingsConfigDict(
        env_prefix="PGO_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Root ────────────────────────────────────────────────
    repo_root: Path | None = None

    # ── Derived directory paths ─────────────────────────────
    manifests_dir: Path | None = None
    vault_dir: Path | None = None
    data_dir: Path | None = None
    reports_dir: Path | None = None
    exports_dir: Path | None = None

    # ── Manifest settings ───────────────────────────────────
    manifest_filename: str = "brokers_manifest.yaml"
    manifest_max_size_kb: int = 512  # reject manifests > 512 KB

    # ── Logging ─────────────────────────────────────────────
    log_level: str = "INFO"
    log_json: bool = True  # structured JSON by default

    # ── Vault ───────────────────────────────────────────────
    vault_encryption_key_env: str = "PGO_VAULT_KEY"

    @model_validator(mode="after")
    def _resolve_paths(self) -> "Settings":
        """Fill in any path that was not explicitly overridden."""
        if self.repo_root is None:
            self.repo_root = find_repo_root()

        root = self.repo_root
        defaults: dict[str, Path] = {
            "manifests_dir": root / "manifests",
            "vault_dir": root / "vault",
            "data_dir": root / "data",
            "reports_dir": root / "reports",
            "exports_dir": root / "exports",
        }
        for attr, default_val in defaults.items():
            if getattr(self, attr) is None:
                setattr(self, attr, default_val)
        return self

    # ── Convenience ─────────────────────────────────────────
    @property
    def manifest_path(self) -> Path:
        """Full path to the active broker manifest."""
        assert self.manifests_dir is not None  # guaranteed after validation
        return self.manifests_dir / self.manifest_filename

    def ensure_dirs(self) -> None:
        """Create all local-state directories if they don't exist."""
        for d in (self.vault_dir, self.data_dir, self.reports_dir, self.exports_dir):
            assert d is not None  # guaranteed after validation
            d.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings(**overrides: object) -> Settings:
    """Return a cached :class:`Settings` instance.

    In production the cache avoids repeated filesystem walks.
    In tests, call ``Settings(repo_root=tmp_path)`` directly.
    """
    return Settings(**overrides)  # type: ignore[arg-type]
