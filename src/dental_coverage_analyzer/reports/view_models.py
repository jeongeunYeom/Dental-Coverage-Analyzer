from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from dental_coverage_analyzer.models import (
    AggregateCoverage, CustomerInfo, DentalRider, InsuranceContract,
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


def build_report_data(
    customer: CustomerInfo,
    aggregates: list[AggregateCoverage],
    contracts: list[InsuranceContract],
    riders: list[DentalRider],
) -> ReportData:
    return ReportData(
        customer_name=customer.name or customer.masked_name or "정보 없음",
        analysis_date=customer.analysis_date or date.today(),
        aggregates=tuple(ReportAggregate(
            item.raw_name, item.category or "기타 치과", item.recommended_amount,
            item.enrolled_amount, item.normalized_shortage if item.normalized_shortage is not None else item.shortage_amount,
            item.calculate_ratio(), item.status,
        ) for item in aggregates),
        contracts=tuple(ReportContract(
            item.insurer, item.product_name, item.coverage_period, item.monthly_premium,
        ) for item in contracts),
        riders=tuple(ReportRider(
            item.raw_name, item.category or "기타 치과", item.insurer, item.product_name,
            item.enrolled_amount,
            {"DISEASE": "질병", "ACCIDENT": "상해", "BOTH": "질병/상해", "UNKNOWN": "확인 필요"}[item.cause_type.value],
            {"PER_TOOTH": "치아당", "PER_OCCURRENCE": "회/촬영당", "PER_YEAR": "연간", "PER_TREATMENT": "치료당", "UNKNOWN": "확인 필요"}[item.payment_unit.value],
        ) for item in riders),
    )
