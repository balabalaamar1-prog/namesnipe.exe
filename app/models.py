"""Shared data types."""
from dataclasses import dataclass
from enum import Enum


class Status(str, Enum):
    AVAILABLE = "available"
    TAKEN = "taken"
    INVALID = "invalid"
    RATE_LIMITED = "rate_limited"
    ERROR = "error"


@dataclass(frozen=True)
class Result:
    name: str
    status: Status
    detail: str = ""
    retry_after: float = 0.0  # seconds; only meaningful for RATE_LIMITED
