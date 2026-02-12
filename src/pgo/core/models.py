"""PGO domain models — enums and core value objects."""

from enum import Enum


class FindingStatus(str, Enum):
    DISCOVERED = "discovered"
    CONFIRMED = "confirmed"
    SUBMITTED = "submitted"
    PENDING = "pending"
    VERIFIED = "verified"
    RESURFACED = "resurfaced"
