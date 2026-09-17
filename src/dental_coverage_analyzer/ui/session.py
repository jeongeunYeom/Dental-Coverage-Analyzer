from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import date

from dental_coverage_analyzer.core.pdf import PDFAnalysisResult
from dental_coverage_analyzer.core.processing import select_canonical_aggregates
from dental_coverage_analyzer.models import (
    AggregateCoverage, CauseType, Confidence, CustomerInfo, DentalRider,
    InsuranceContract, PaymentUnit,
)


@dataclass(slots=True)
class AnalysisSession:
    source_path: str
    customer: CustomerInfo = field(default_factory=lambda: CustomerInfo(analysis_date=date.today()))
    contracts: list[InsuranceContract] = field(default_factory=list)
    aggregates: list[AggregateCoverage] = field(default_factory=list)
    riders: list[DentalRider] = field(default_factory=list)
    result: PDFAnalysisResult | None = None
    raw_aggregate_candidates: list[AggregateCoverage] = field(default_factory=list)
    aggregate_conflict_warnings: list[str] = field(default_factory=list)
    comment: str = ""

    @classmethod
    def from_result(cls, source_path: str, result: PDFAnalysisResult) -> "AnalysisSession":
        raw_candidates = deepcopy(result.aggregate_coverages)
        canonical = select_canonical_aggregates(raw_candidates)
        return cls(
            source_path=source_path,
            customer=CustomerInfo(analysis_date=date.today()),
            contracts=deepcopy(result.contracts),
            aggregates=list(canonical.aggregates),
            raw_aggregate_candidates=raw_candidates,
            aggregate_conflict_warnings=list(canonical.warnings),
            riders=deepcopy(result.dental_riders),
            result=result,
        )

    def add_aggregate(self) -> AggregateCoverage:
        item = AggregateCoverage("새 전체 보장", confidence=Confidence.LOW, confidence_reason="사용자 추가")
        self.aggregates.append(item)
        self.raw_aggregate_candidates.append(item)
        return item

    def add_rider(self) -> DentalRider:
        item = DentalRider("새 세부 담보", confidence=Confidence.LOW, confidence_reason="사용자 추가")
        self.riders.append(item)
        return item


def parse_optional_int(text: str) -> int | None:
    value = text.strip().replace(",", "").replace("원", "")
    if not value or value == "정보 없음":
        return None
    return int(value)


def parse_cause(text: str) -> CauseType:
    korean = {"질병": CauseType.DISEASE, "상해": CauseType.ACCIDENT, "질병/상해": CauseType.BOTH, "확인 필요": CauseType.UNKNOWN}
    if text.strip() in korean:
        return korean[text.strip()]
    try:
        return CauseType(text.strip())
    except ValueError:
        return CauseType.UNKNOWN


def parse_payment_unit(text: str) -> PaymentUnit:
    korean = {
        "치아당": PaymentUnit.PER_TOOTH, "회/촬영당": PaymentUnit.PER_OCCURRENCE,
        "연간": PaymentUnit.PER_YEAR, "치료당": PaymentUnit.PER_TREATMENT,
        "확인 필요": PaymentUnit.UNKNOWN,
    }
    if text.strip() in korean:
        return korean[text.strip()]
    try:
        return PaymentUnit(text.strip())
    except ValueError:
        return PaymentUnit.UNKNOWN


def optional_text(text: str) -> str | None:
    value = text.strip()
    return None if not value or value == "정보 없음" else value


def cause_label(value: CauseType) -> str:
    return {CauseType.DISEASE: "질병", CauseType.ACCIDENT: "상해", CauseType.BOTH: "질병/상해", CauseType.UNKNOWN: "확인 필요"}[value]


def payment_label(value: PaymentUnit) -> str:
    return {PaymentUnit.PER_TOOTH: "치아당", PaymentUnit.PER_OCCURRENCE: "회/촬영당", PaymentUnit.PER_YEAR: "연간", PaymentUnit.PER_TREATMENT: "치료당", PaymentUnit.UNKNOWN: "확인 필요"}[value]
