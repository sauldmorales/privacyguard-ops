"""Broker manifest loader.

Loads ``brokers_manifest.yaml`` with safety guards:

* Size limit (default 512 KB) — rejects oversized files.
* ``yaml.safe_load`` only — no arbitrary Python objects.
* Encoding validated (UTF-8).
* Typed exceptions (:class:`ManifestNotFound`, :class:`ManifestInvalid`,
  :class:`ManifestTooLarge`).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, field_validator

from pgo.core.errors import ManifestInvalid, ManifestNotFound, ManifestTooLarge

# Default max manifest size (bytes).
_DEFAULT_MAX_SIZE_BYTES = 512 * 1024  # 512 KB


# ── Pydantic v2 strict models ──────────────────────────────
class BrokerTarget(BaseModel):
    """A single broker entry from the manifest."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    id: str | None = None
    domain: str | None = None
    url: str | None = None
    status: str | None = None
    notes: str | None = None
    workflow: list[dict[str, str]] | None = None

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("broker name must not be blank")
        return v


# ── Loader ──────────────────────────────────────────────────
def load_brokers_manifest(
    path: Path,
    *,
    max_size_bytes: int = _DEFAULT_MAX_SIZE_BYTES,
) -> list[BrokerTarget]:
    """Load and validate brokers manifest YAML.

    Parameters
    ----------
    path:
        Absolute or resolved path to the manifest file.
    max_size_bytes:
        Reject files larger than this (defence-in-depth).

    Returns
    -------
    list[BrokerTarget]
        Validated broker entries.

    Raises
    ------
    ManifestNotFound
        File does not exist.
    ManifestTooLarge
        File exceeds *max_size_bytes*.
    ManifestInvalid
        YAML parse error or schema validation failure.
    """
    if not path.exists():
        raise ManifestNotFound(f"manifest not found: {path}")

    # Size guard.
    size = path.stat().st_size
    if size > max_size_bytes:
        raise ManifestTooLarge(
            f"manifest {path.name} is {size:,} bytes (limit {max_size_bytes:,})"
        )

    # Read + parse.
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ManifestInvalid(f"manifest is not valid UTF-8: {exc}") from exc

    try:
        raw: Any = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ManifestInvalid(f"YAML parse error: {exc}") from exc

    if raw is None:
        return []

    # Accept {"brokers": [...]} or bare [...]
    if isinstance(raw, dict) and "brokers" in raw:
        items = raw["brokers"]
    elif isinstance(raw, list):
        items = raw
    else:
        raise ManifestInvalid("manifest schema invalid: expected list or {'brokers': list}")

    if not isinstance(items, list):
        raise ManifestInvalid("manifest 'brokers' key must contain a list")

    # Validate each entry through Pydantic.
    out: list[BrokerTarget] = []
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            raise ManifestInvalid(f"manifest item #{i} must be a mapping")

        # Normalise legacy key "broker" → "name".
        if "broker" in item and "name" not in item:
            item["name"] = item.pop("broker")

        try:
            out.append(BrokerTarget.model_validate(item))
        except Exception as exc:
            raise ManifestInvalid(f"manifest item #{i}: {exc}") from exc

    return out
