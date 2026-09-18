from __future__ import annotations

from dataclasses import dataclass

from dental_coverage_analyzer.models import AggregateCoverage


@dataclass(frozen=True, slots=True)
class NormalizedAggregateValues:
    status: str
    shortage: int | None
    ratio: float | None


def normalize_aggregate_status(
    recommended_amount: int | None,
    enrolled_amount: int | None,
    existing_status: str | None = None,
) -> str:
    """확인된 금액이 충분할 때만 고객 표시용 상태를 계산한다."""
    if recommended_amount is None or enrolled_amount is None:
        return existing_status or "정보 확인 필요"
    if recommended_amount <= 0:
        return "정보 확인 필요"
    if enrolled_amount == 0:
        return "미가입"
    if enrolled_amount < recommended_amount:
        return "부족"
    return "충분"


def normalize_aggregate_values(item: AggregateCoverage) -> NormalizedAggregateValues:
    recommended = item.recommended_amount
    enrolled = item.enrolled_amount
    status = normalize_aggregate_status(recommended, enrolled, item.status)
    if recommended is not None and recommended > 0 and enrolled is not None:
        shortage = max(recommended - enrolled, 0)
        ratio = enrolled / recommended * 100
    else:
        shortage = item.normalized_shortage
        ratio = None
    return NormalizedAggregateValues(status, shortage, ratio)
