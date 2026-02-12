from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from pgo.core.errors import StateTransitionInvalid
from pgo.core.models import FindingStatus


# Reglas: de dónde a dónde se puede mover
ALLOWED_TRANSITIONS: dict[FindingStatus, set[FindingStatus]] = {
    FindingStatus.DISCOVERED: {FindingStatus.CONFIRMED},
    FindingStatus.CONFIRMED: {FindingStatus.SUBMITTED},
    FindingStatus.SUBMITTED: {FindingStatus.PENDING, FindingStatus.VERIFIED},
    FindingStatus.PENDING: {FindingStatus.VERIFIED, FindingStatus.RESURFACED},
    FindingStatus.VERIFIED: {FindingStatus.RESURFACED},
    FindingStatus.RESURFACED: {FindingStatus.SUBMITTED},  # opcional: reintento
}


@dataclass(frozen=True)
class TransitionEvent:
    finding_id: str
    from_status: FindingStatus
    to_status: FindingStatus
    at_utc: str  # ISO string


def can_transition(from_status: FindingStatus, to_status: FindingStatus) -> bool:
    return to_status in ALLOWED_TRANSITIONS.get(from_status, set())


def transition(finding_id: str, from_status: FindingStatus, to_status: FindingStatus) -> TransitionEvent:
    if not can_transition(from_status, to_status):
        raise StateTransitionInvalid(from_status.value, to_status.value)

    ts = datetime.now(timezone.utc).isoformat()
    return TransitionEvent(
        finding_id=finding_id,
        from_status=from_status,
        to_status=to_status,
        at_utc=ts,
    )
