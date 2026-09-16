from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Confidence(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class CauseType(StrEnum):
    DISEASE = "DISEASE"
    ACCIDENT = "ACCIDENT"
    BOTH = "BOTH"
    UNKNOWN = "UNKNOWN"


class PaymentUnit(StrEnum):
    PER_TOOTH = "PER_TOOTH"
    PER_OCCURRENCE = "PER_OCCURRENCE"
    PER_YEAR = "PER_YEAR"
    PER_TREATMENT = "PER_TREATMENT"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class SourceReference:
    page: int
    bbox: tuple[float, float, float, float] | None = None
    raw_text: str | None = None

    def __post_init__(self) -> None:
        if self.page < 1:
            raise ValueError("source page는 1 이상이어야 합니다")
        if self.bbox is not None:
            x0, y0, x1, y1 = self.bbox
            if x1 < x0 or y1 < y0:
                raise ValueError("bbox 좌표 순서가 올바르지 않습니다")
