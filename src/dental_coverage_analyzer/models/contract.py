from dataclasses import dataclass, field
from datetime import date

from .common import Confidence, SourceReference


@dataclass(slots=True)
class InsuranceContract:
    insurer: str | None = None
    product_name: str | None = None
    policyholder: str | None = None
    insured_person: str | None = None
    enrollment_date: date | None = None
    coverage_period: str | None = None
    payment_period: str | None = None
    payment_cycle: str | None = None
    maturity: str | None = None
    monthly_premium: int | None = None
    contract_status: str | None = None
    sources: list[SourceReference] = field(default_factory=list)
    confidence: Confidence = Confidence.LOW
    confidence_reason: str = "확인 가능한 계약 근거가 부족함"
