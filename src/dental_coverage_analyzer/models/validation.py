from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class ValidationSeverity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


@dataclass(slots=True)
class ValidationIssue:
    code: str
    severity: ValidationSeverity
    message: str
    page_numbers: list[int] = field(default_factory=list)
    related_object_type: str | None = None
    related_object_id: str | None = None
    raw_values: list[str] = field(default_factory=list)

