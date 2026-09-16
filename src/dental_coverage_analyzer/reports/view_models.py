from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from dental_coverage_analyzer.models import (
    AggregateCoverage, CustomerInfo, DentalRider, InsuranceContract,
    ValidationIssue,
)
from dental_coverage_analyzer.core.processing import (
    AggregateValidity, assess_aggregate, select_canonical_aggregates,
)


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
    recommended = item.recommended_amount if item.recommended_amount and item.recommended_amount > 0 else None
    ratio = item.enrolled_amount / recommended * 100 if recommended is not None and item.enrolled_amount is not None else None
    shortage = item.normalized_shortage if item.normalized_shortage is not None else item.shortage_amount
    needs_review = assessment.validity is not AggregateValidity.VALID
    return ReportAggregate(
        item.raw_name, item.category or "기타 치과", recommended, item.enrolled_amount,
        shortage, ratio, "정보 확인 필요" if needs_review else item.status,
        item.confidence.value, None if _first_page(item) == 10**9 else _first_page(item), needs_review,
    )


def build_report_data(
    customer: CustomerInfo,
    aggregates: list[AggregateCoverage],
    contracts: list[InsuranceContract],
    riders: list[DentalRider],
    validation_issues: list[ValidationIssue] | None = None,
) -> ReportData:
    representatives, warnings = select_representative_aggregates(aggregates)
    return ReportData(
        customer_name=customer.name or customer.masked_name or "정보 없음",
        analysis_date=customer.analysis_date or date.today(),
        aggregates=tuple(_to_report_aggregate(item) for item in representatives),
        contracts=tuple(ReportContract(
            item.insurer, item.product_name, item.coverage_period, item.monthly_premium,
        ) for item in contracts),
        riders=tuple(ReportRider(
            item.raw_name, item.category or "기타 치과", item.insurer, item.product_name,
            item.enrolled_amount,
            {"DISEASE": "질병", "ACCIDENT": "상해", "BOTH": "질병/상해", "UNKNOWN": "확인 필요"}[item.cause_type.value],
            {"PER_TOOTH": "치아당", "PER_OCCURRENCE": "회/촬영당", "PER_YEAR": "연간", "PER_TREATMENT": "치료당", "UNKNOWN": "확인 필요"}[item.payment_unit.value],
        ) for item in riders),
        aggregate_warnings=tuple(warnings),
        validation_issues=tuple(validation_issues or ()),
    )
