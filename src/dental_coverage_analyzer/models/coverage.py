from dataclasses import dataclass, field

from .common import CauseType, Confidence, PaymentUnit, SourceReference


@dataclass(slots=True)
class AggregateCoverage:
    raw_name: str
    normalized_name: str | None = None
    category: str | None = None
    recommended_amount: int | None = None
    enrolled_amount: int | None = None
    shortage_amount: int | None = None
    surplus_amount: int | None = None
    raw_difference: str | None = None
    normalized_shortage: int | None = None
    normalized_surplus: int | None = None
    reported_ratio: float | None = None
    calculated_ratio: float | None = None
    status: str | None = None
    normalized_status: str = "UNKNOWN"
    source_pages: list[int] = field(default_factory=list)
    representative_source: SourceReference | None = None
    confidence: Confidence = Confidence.LOW
    confidence_reason: str = "자동 추출 결과를 검토해야 함"

    def calculate_ratio(self) -> float | None:
        if self.recommended_amount is None or self.enrolled_amount is None:
            return None
        if self.recommended_amount <= 0:
            return None
        return self.enrolled_amount / self.recommended_amount * 100


@dataclass(slots=True)
class DentalRider:
    raw_name: str
    insurer: str | None = None
    product_name: str | None = None
    normalized_name: str | None = None
    credit_information_name: str | None = None
    category: str | None = None
    subcategory: str | None = None
    enrolled_amount: int | None = None
    raw_amount: str | None = None
    payment_unit: PaymentUnit = PaymentUnit.UNKNOWN
    payment_limit: str | None = None
    cause_type: CauseType = CauseType.UNKNOWN
    source: SourceReference | None = None
    confidence: Confidence = Confidence.LOW
    confidence_reason: str = "자동 추출 결과를 검토해야 함"
    raw_text: str | None = None
