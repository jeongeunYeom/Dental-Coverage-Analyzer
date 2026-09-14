from dataclasses import dataclass
from enum import StrEnum

from .common import Confidence


class SupportLevel(StrEnum):
    FULL = "FULL"
    PARTIAL = "PARTIAL"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    UNSUPPORTED = "UNSUPPORTED"


@dataclass(slots=True)
class ParserSupportSummary:
    provider: str
    provider_confidence: Confidence
    provider_reason: str
    text_layer_pages: int
    ocr_attempted_pages: int
    ocr_success_pages: int
    ocr_failed_pages: int
    contracts_found: int
    aggregate_found: int
    riders_found: int
    review_required: int
    support_level: SupportLevel
