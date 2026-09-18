from dental_coverage_analyzer.core.processing import (
    AggregateValidity, assess_aggregate, select_canonical_aggregates,
)
from dental_coverage_analyzer.models import AggregateCoverage, Confidence, SourceReference


def candidate(name, category, recommended, enrolled, shortage, status, confidence, page):
    return AggregateCoverage(
        name, normalized_name="".join(name.split()), category=category,
        recommended_amount=recommended, enrolled_amount=enrolled,
        shortage_amount=shortage, normalized_shortage=(
            max(recommended - enrolled, 0)
            if recommended is not None and enrolled is not None and recommended > 0 else None
        ),
        status=status, confidence=confidence, source_pages=[page],
        representative_source=SourceReference(page, raw_text=f"synthetic page {page}"),
    )


def actual_conflicting_candidates():
    return [
        candidate("치아보철 치료비", "보철치료", 2_000_000, 500_000, 1_500_000, "부족", Confidence.MEDIUM, 6),
        candidate("치아보철 치료비", "보철치료", 500_000, None, 1_500_000, "부족", Confidence.HIGH, 19),
        candidate("치아보존 치료비", "보존치료", 500_000, 0, 500_000, "미가입", Confidence.MEDIUM, 6),
        candidate("치아보존 치료비", "보존치료", 0, 500_000, 0, "미가입", Confidence.HIGH, 19),
    ]


def test_actual_high_confidence_bad_candidates_never_override_valid_rows():
    candidates = actual_conflicting_candidates()
    result = select_canonical_aggregates(candidates)
    assert len(result.aggregates) == 2
    prosthetic, restorative = result.aggregates
    assert (prosthetic.recommended_amount, prosthetic.enrolled_amount, prosthetic.shortage_amount, prosthetic.status) == (
        2_000_000, 500_000, 1_500_000, "부족",
    )
    assert (restorative.recommended_amount, restorative.enrolled_amount, restorative.shortage_amount, restorative.status) == (
        500_000, 0, 500_000, "미가입",
    )
    assert len(result.conflicting_candidates) == 2
    assert len(result.warnings) == 2
    assert "page 6" in result.warnings[0] and "page 19" in result.warnings[0]


def test_aggregate_status_validation_rules_are_strict():
    valid, incomplete, invalid = actual_conflicting_candidates()[0], actual_conflicting_candidates()[1], actual_conflicting_candidates()[3]
    assert assess_aggregate(valid).validity is AggregateValidity.VALID
    assert assess_aggregate(incomplete).validity is AggregateValidity.INCOMPLETE
    assert assess_aggregate(invalid).validity is AggregateValidity.INVALID
