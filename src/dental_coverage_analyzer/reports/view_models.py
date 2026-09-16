from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from dental_coverage_analyzer.models import (
    AggregateCoverage, Confidence, CustomerInfo, DentalRider, InsuranceContract,
    ValidationIssue,
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


_CONFIDENCE_SCORE = {Confidence.HIGH: 3, Confidence.MEDIUM: 2, Confidence.LOW: 1}
_MAIN_CATEGORIES = {"보철치료", "보존치료"}


def _logical_score(item: AggregateCoverage) -> int:
    recommended, enrolled = item.recommended_amount, item.enrolled_amount
    if recommended is not None and recommended <= 0:
        return 0
    if enrolled is not None and enrolled > 0 and item.status == "미가입":
        return 0
    if recommended is not None and enrolled is not None:
        shortage = max(recommended - enrolled, 0)
        known_shortage = item.normalized_shortage if item.normalized_shortage is not None else item.shortage_amount
        if known_shortage is not None and known_shortage != shortage:
            return 0
        return 2
    return 1


def _source_score(item: AggregateCoverage) -> int:
    source = item.representative_source
    return int(bool(source and source.raw_text)) + int(bool(source and source.bbox))


def _first_page(item: AggregateCoverage) -> int:
    pages = list(item.source_pages)
    if item.representative_source:
        pages.append(item.representative_source.page)
    return min(pages) if pages else 10**9


def _representative_rank(item: AggregateCoverage) -> tuple[int, int, int, int, int]:
    complete = int(item.recommended_amount is not None and item.enrolled_amount is not None)
    return (
        _CONFIDENCE_SCORE.get(item.confidence, 0), complete, _logical_score(item),
        _source_score(item), -_first_page(item),
    )


def _group_key(item: AggregateCoverage) -> str:
    if item.category in _MAIN_CATEGORIES:
        return item.category
    return item.normalized_name or "".join(item.raw_name.split())


def _signature(item: AggregateCoverage) -> tuple:
    return item.recommended_amount, item.enrolled_amount, item.status


def select_representative_aggregates(
    aggregates: list[AggregateCoverage],
) -> tuple[list[AggregateCoverage], list[str]]:
    """원본 후보는 변경하지 않고 보고서용 대표값과 충돌 안내만 만든다."""
    groups: dict[str, list[AggregateCoverage]] = {}
    order: list[str] = []
    for item in aggregates:
        key = _group_key(item)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(item)
    selected: list[AggregateCoverage] = []
    warnings: list[str] = []
    for key in order:
        candidates = groups[key]
        selected.append(max(candidates, key=_representative_rank))
        if len({_signature(item) for item in candidates}) > 1:
            label = key if key in _MAIN_CATEGORIES else candidates[0].raw_name
            warnings.append(
                f"원본 자료에서 '{label}'의 서로 다른 값이 확인되어 신뢰도가 높은 값을 대표값으로 표시했습니다. "
                "상세 내용은 ‘확인 필요’ 항목을 확인하세요."
            )
    return selected, warnings


def _to_report_aggregate(item: AggregateCoverage) -> ReportAggregate:
    logical = _logical_score(item)
    recommended = item.recommended_amount if item.recommended_amount and item.recommended_amount > 0 else None
    ratio = item.enrolled_amount / recommended * 100 if recommended is not None and item.enrolled_amount is not None else None
    shortage = item.normalized_shortage if item.normalized_shortage is not None else item.shortage_amount
    needs_review = logical == 0 or item.recommended_amount is None or item.enrolled_amount is None
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
