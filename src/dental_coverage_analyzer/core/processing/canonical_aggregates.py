from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

from dental_coverage_analyzer.models import AggregateCoverage, Confidence


class AggregateValidity(IntEnum):
    INVALID = 0
    INCOMPLETE = 1
    VALID = 2


@dataclass(frozen=True, slots=True)
class AggregateAssessment:
    validity: AggregateValidity
    complete: bool
    mathematically_consistent: bool
    structural_evidence: int
    source_reliability: int
    reason: str


@dataclass(frozen=True, slots=True)
class CanonicalAggregateSelection:
    aggregates: tuple[AggregateCoverage, ...]
    warnings: tuple[str, ...]
    conflicting_candidates: tuple[AggregateCoverage, ...]


_CONFIDENCE_SCORE = {Confidence.HIGH: 3, Confidence.MEDIUM: 2, Confidence.LOW: 1}
_MAIN_CATEGORIES = {"보철치료", "보존치료"}


def _difference(item: AggregateCoverage) -> int | None:
    if item.shortage_amount is not None:
        return item.shortage_amount
    return item.normalized_shortage


def assess_aggregate(item: AggregateCoverage) -> AggregateAssessment:
    """금액과 원본 상태의 논리 관계를 보수적으로 평가한다."""
    recommended = item.recommended_amount
    enrolled = item.enrolled_amount
    shortage = _difference(item)
    status = (item.status or "").strip()
    complete = recommended is not None and enrolled is not None
    consistent = False
    reason = "필수 금액이 일부 확인되지 않음"

    if recommended is not None and recommended <= 0:
        validity = AggregateValidity.INVALID
        reason = "권장금액이 0 이하임"
    elif status == "부족":
        if not complete or shortage is None:
            validity = AggregateValidity.INCOMPLETE
            reason = "부족 상태의 권장/가입/부족금액이 모두 확인되지 않음"
        else:
            consistent = recommended > enrolled and recommended - enrolled == shortage
            validity = AggregateValidity.VALID if consistent else AggregateValidity.INVALID
            reason = "부족 상태와 금액이 일치함" if consistent else "부족 상태와 금액 계산이 일치하지 않음"
    elif status == "미가입":
        if not complete or shortage is None:
            validity = AggregateValidity.INCOMPLETE
            reason = "미가입 상태의 권장/가입/부족금액이 모두 확인되지 않음"
        else:
            consistent = recommended > 0 and enrolled == 0 and shortage == recommended
            validity = AggregateValidity.VALID if consistent else AggregateValidity.INVALID
            reason = "미가입 상태와 금액이 일치함" if consistent else "미가입 상태와 금액 계산이 일치하지 않음"
    elif status in {"충분", "적정"}:
        if not complete:
            validity = AggregateValidity.INCOMPLETE
            reason = "충분 상태의 권장/가입금액이 모두 확인되지 않음"
        else:
            consistent = enrolled >= recommended
            validity = AggregateValidity.VALID if consistent else AggregateValidity.INVALID
            reason = "충분 상태와 금액이 일치함" if consistent else "충분 상태인데 가입금액이 권장금액보다 작음"
    elif status == "초과":
        if not complete:
            validity = AggregateValidity.INCOMPLETE
            reason = "초과 상태의 권장/가입금액이 모두 확인되지 않음"
        else:
            consistent = enrolled > recommended
            validity = AggregateValidity.VALID if consistent else AggregateValidity.INVALID
            reason = "초과 상태와 금액이 일치함" if consistent else "초과 상태와 금액이 일치하지 않음"
    elif complete:
        expected_shortage = max(recommended - enrolled, 0)
        consistent = recommended > 0 and (shortage is None or shortage == expected_shortage)
        validity = AggregateValidity.VALID if consistent else AggregateValidity.INVALID
        reason = (
            "권장/가입금액은 확인되었으나 상태 확인 필요"
            if consistent else "원문 부족금액과 권장/가입금액 계산이 일치하지 않음"
        )
    else:
        validity = AggregateValidity.INCOMPLETE

    evidence = item.confidence_reason or ""
    structural = 2 if "bbox" in evidence and "header" in evidence else 1 if "명시적 필드 label" in evidence else 0
    page_reliability = 2 if any(value in evidence for value in ("COVERAGE_ANALYSIS", "COVERAGE_DETAIL")) else 1 if "SUMMARY" in evidence else 0
    return AggregateAssessment(validity, complete, consistent, structural, page_reliability, reason)


def _first_page(item: AggregateCoverage) -> int:
    pages = list(item.source_pages)
    if item.representative_source:
        pages.append(item.representative_source.page)
    return min(pages) if pages else 10**9


def _rank(item: AggregateCoverage) -> tuple[int, int, int, int, int, int, int]:
    assessment = assess_aggregate(item)
    return (
        int(assessment.validity),
        int(assessment.complete),
        int(assessment.mathematically_consistent),
        assessment.structural_evidence,
        assessment.source_reliability,
        _CONFIDENCE_SCORE.get(item.confidence, 0),
        -_first_page(item),
    )


def _group_key(item: AggregateCoverage) -> str:
    if item.category in _MAIN_CATEGORIES:
        return item.category
    return item.normalized_name or "".join(item.raw_name.split())


def _signature(item: AggregateCoverage) -> tuple[object, ...]:
    return item.recommended_amount, item.enrolled_amount, _difference(item), item.status


def _describe(item: AggregateCoverage) -> str:
    page = _first_page(item)
    return (
        f"page {page if page != 10**9 else '정보 없음'}: 권장={item.recommended_amount}, "
        f"가입={item.enrolled_amount}, 부족={_difference(item)}, 상태={item.status or '정보 없음'}"
    )


def select_canonical_aggregates(candidates: list[AggregateCoverage]) -> CanonicalAggregateSelection:
    """raw candidate를 변경하지 않고 사용자 표시용 canonical 항목을 고른다."""
    groups: dict[str, list[AggregateCoverage]] = {}
    order: list[str] = []
    for item in candidates:
        key = _group_key(item)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(item)

    selected: list[AggregateCoverage] = []
    warnings: list[str] = []
    conflicts: list[AggregateCoverage] = []
    for key in order:
        group = groups[key]
        valid = [item for item in group if assess_aggregate(item).validity is AggregateValidity.VALID]
        representative = max(valid or group, key=_rank)
        selected.append(representative)
        if len({_signature(item) for item in group}) > 1:
            conflicts.extend(item for item in group if item is not representative)
            detail = "; ".join(_describe(item) for item in group)
            warnings.append(
                f"'{key}'이(가) 여러 페이지에서 서로 다른 값으로 추출되었습니다. "
                f"대표값은 {_describe(representative)}입니다. 후보: {detail}"
            )
    return CanonicalAggregateSelection(tuple(selected), tuple(warnings), tuple(conflicts))
