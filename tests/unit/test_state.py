"""Tests for pgo.state — state machine transitions."""

from __future__ import annotations

import pytest

from pgo.core.errors import StateTransitionInvalid
from pgo.models import FindingStatus
from pgo.state import ALLOWED_TRANSITIONS, can_transition, transition


# ── Valid transitions ───────────────────────────────────────
@pytest.mark.parametrize(
    "from_s, to_s",
    [
        (FindingStatus.DISCOVERED, FindingStatus.CONFIRMED),
        (FindingStatus.CONFIRMED, FindingStatus.SUBMITTED),
        (FindingStatus.SUBMITTED, FindingStatus.PENDING),
        (FindingStatus.SUBMITTED, FindingStatus.VERIFIED),
        (FindingStatus.PENDING, FindingStatus.VERIFIED),
        (FindingStatus.PENDING, FindingStatus.RESURFACED),
        (FindingStatus.VERIFIED, FindingStatus.RESURFACED),
        (FindingStatus.RESURFACED, FindingStatus.SUBMITTED),
    ],
)
def test_valid_transitions(from_s: FindingStatus, to_s: FindingStatus) -> None:
    assert can_transition(from_s, to_s) is True
    event = transition("f-1", from_s, to_s)
    assert event.from_status == from_s
    assert event.to_status == to_s
    assert event.finding_id == "f-1"
    assert event.at_utc  # non-empty ISO string


# ── Invalid transitions ────────────────────────────────────
@pytest.mark.parametrize(
    "from_s, to_s",
    [
        (FindingStatus.DISCOVERED, FindingStatus.VERIFIED),
        (FindingStatus.DISCOVERED, FindingStatus.SUBMITTED),
        (FindingStatus.CONFIRMED, FindingStatus.VERIFIED),
        (FindingStatus.VERIFIED, FindingStatus.DISCOVERED),
        (FindingStatus.PENDING, FindingStatus.DISCOVERED),
    ],
)
def test_invalid_transitions(from_s: FindingStatus, to_s: FindingStatus) -> None:
    assert can_transition(from_s, to_s) is False
    with pytest.raises(StateTransitionInvalid):
        transition("f-1", from_s, to_s)


# ── Coverage: every status has an entry in ALLOWED_TRANSITIONS ──
def test_all_statuses_have_transition_rules() -> None:
    for status in FindingStatus:
        assert status in ALLOWED_TRANSITIONS, f"{status} missing from ALLOWED_TRANSITIONS"
