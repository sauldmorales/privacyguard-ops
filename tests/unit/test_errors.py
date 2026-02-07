"""Tests for pgo.core.errors — typed domain exceptions."""

from __future__ import annotations

from pgo.core.errors import (
    AuditChainBroken,
    ManifestInvalid,
    ManifestNotFound,
    ManifestTooLarge,
    PGOError,
    RepoRootNotFound,
    StateTransitionInvalid,
    VaultKeyMissing,
    VaultWriteFailed,
)


def test_all_errors_inherit_from_pgo_error() -> None:
    """Every domain exception must be catchable as PGOError."""
    exceptions: list[PGOError] = [
        RepoRootNotFound(),
        ManifestNotFound("x"),
        ManifestInvalid("x"),
        ManifestTooLarge("x"),
        StateTransitionInvalid("a", "b"),
        AuditChainBroken("x"),
        VaultWriteFailed("x"),
        VaultKeyMissing("x"),
    ]
    for exc in exceptions:
        assert isinstance(exc, PGOError), f"{type(exc).__name__} does not inherit PGOError"


def test_repo_root_not_found_message() -> None:
    exc = RepoRootNotFound(start_path="/some/path")
    assert "/some/path" in str(exc)
    assert exc.start_path == "/some/path"


def test_state_transition_invalid_attrs() -> None:
    exc = StateTransitionInvalid("discovered", "verified")
    assert exc.from_status == "discovered"
    assert exc.to_status == "verified"
    assert "discovered" in str(exc) and "verified" in str(exc)
