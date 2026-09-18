from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from dental_coverage_analyzer.models import (
    AggregateCoverage, Confidence, CustomerInfo, DentalRider, InsuranceContract,
    ValidationIssue,
)
from dental_coverage_analyzer.branding import BrandingSettings
from dental_coverage_analyzer.core.processing import (
    AggregateValidity, assess_aggregate, normalize_aggregate_values,
    select_canonical_aggregates,
)
from dental_coverage_analyzer.core.dental import DentalProductDetector


@dataclass(frozen=True, slots=True)
class ReportAggregate:
    name: str
    category: str
    recommended_amount: int | None
    enrolled_amount: int | None
    shortage_amount: int | None
    ratio: float | None
    status: str | None
    confidence: str
    source_page: int | None
    needs_review: bool = False


@dataclass(frozen=True, slots=True)
class ReportContract:
    insurer: str | None
    product_name: str | None
    coverage_period: str | None
    monthly_premium: int | None


@dataclass(frozen=True, slots=True)
class ReportRider:
    name: str
    category: str
    insurer: str | None
    product_name: str | None
    amount: int | None
    cause_type: str
    payment_unit: str


@dataclass(frozen=True, slots=True)
class ReportData:
    customer_name: str
    analysis_date: date
    aggregates: tuple[ReportAggregate, ...] = field(default_factory=tuple)
    contracts: tuple[ReportContract, ...] = field(default_factory=tuple)
    riders: tuple[ReportRider, ...] = field(default_factory=tuple)
    aggregate_warnings: tuple[str, ...] = field(default_factory=tuple)
    validation_issues: tuple[ValidationIssue, ...] = field(default_factory=tuple)
    comment: str = ""
    branding: BrandingSettings = field(default_factory=BrandingSettings)


def _first_page(item: AggregateCoverage) -> int:
    pages = list(item.source_pages)
    if item.representative_source:
        pages.append(item.representative_source.page)
    return min(pages) if pages else 10**9


def select_representative_aggregates(
    aggregates: list[AggregateCoverage],
) -> tuple[list[AggregateCoverage], list[str]]:
    """이전 공개 API를 유지하되 공통 canonical selector를 사용한다."""
    result = select_canonical_aggregates(aggregates)
    return list(result.aggregates), list(result.warnings)


def _to_report_aggregate(item: AggregateCoverage) -> ReportAggregate:
    assessment = assess_aggregate(item)
    normalized = normalize_aggregate_values(item)
    recommended = item.recommended_amount if item.recommended_amount and item.recommended_amount > 0 else None
    needs_review = assessment.validity is not AggregateValidity.VALID
    return ReportAggregate(
        item.raw_name, item.category or "기타 치과", recommended, item.enrolled_amount,
        normalized.shortage, normalized.ratio, normalized.status,
        item.confidence.value, None if _first_page(item) == 10**9 else _first_page(item), needs_review,
    )


def _contract_identity(contract: InsuranceContract) -> str:
    parts = (
        contract.insurer, contract.product_name,
        contract.enrollment_date.isoformat() if contract.enrollment_date else None,
        contract.coverage_period, contract.insured_person,
    )
    values = [value for value in parts if value]
    if not any((contract.enrollment_date, contract.coverage_period, contract.insured_person)):
        values.append("pages=" + ",".join(str(source.page) for source in contract.sources))
    return "|".join(values)


def select_dental_report_contracts(
    contracts: list[InsuranceContract], riders: list[DentalRider],
) -> list[InsuranceContract]:
    detector = DentalProductDetector()
    linked_identities = {
        rider.contract_identity for rider in riders
        if rider.contract_identity and rider.confidence is not Confidence.LOW
    }
    return [
        contract for contract in contracts
        if detector.detect(contract.product_name).is_candidate
        or (_contract_identity(contract) in linked_identities)
    ]


def build_report_data(
    customer: CustomerInfo,
    aggregates: list[AggregateCoverage],
    contracts: list[InsuranceContract],
    riders: list[DentalRider],
    validation_issues: list[ValidationIssue] | None = None,
    comment: str = "",
    branding: BrandingSettings | None = None,
) -> ReportData:
    representatives, warnings = select_representative_aggregates(aggregates)
    dental_contracts = select_dental_report_contracts(contracts, riders)
    customer_warning = (
        "원본 자료에서 일부 보장항목의 값이 서로 다르게 확인되어 검증 가능한 대표값을 표시했습니다. "
        "자세한 내용은 프로그램의 '확인 필요' 탭에서 확인할 수 있습니다."
    )
    return ReportData(
        customer_name=customer.name or customer.masked_name or "정보 없음",
        analysis_date=customer.analysis_date or date.today(),
        aggregates=tuple(_to_report_aggregate(item) for item in representatives),
        contracts=tuple(ReportContract(
            item.insurer, item.product_name, item.coverage_period, item.monthly_premium,
        ) for item in dental_contracts),
        riders=tuple(ReportRider(
            item.raw_name, item.category or "기타 치과", item.insurer, item.product_name,
            item.enrolled_amount,
            {"DISEASE": "질병", "ACCIDENT": "상해", "BOTH": "질병/상해", "UNKNOWN": "확인 필요"}[item.cause_type.value],
            {"PER_TOOTH": "치아당", "PER_OCCURRENCE": "회/촬영당", "PER_YEAR": "연간", "PER_TREATMENT": "치료당", "UNKNOWN": "확인 필요"}[item.payment_unit.value],
        ) for item in riders),
        aggregate_warnings=(customer_warning,) if warnings else (),
        validation_issues=tuple(validation_issues or ()),
        comment=comment,
        branding=branding or BrandingSettings(),
    )
