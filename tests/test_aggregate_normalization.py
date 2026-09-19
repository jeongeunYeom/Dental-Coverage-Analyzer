from dental_coverage_analyzer.core.processing import (
    normalize_aggregate_status, normalize_aggregate_values,
)
from dental_coverage_analyzer.models import AggregateCoverage


def aggregate(recommended, enrolled, status=None, shortage=None):
    return AggregateCoverage(
        "합성 치아보장", recommended_amount=recommended, enrolled_amount=enrolled,
        shortage_amount=shortage, status=status,
    )


def test_meritz_status_shortage_and_ratio_regression():
    prosthetic = normalize_aggregate_values(aggregate(2_000_000, 500_000, "부족", 1_500_000))
    restorative = normalize_aggregate_values(aggregate(500_000, 0, "미가입", 500_000))
    assert (prosthetic.status, prosthetic.shortage, prosthetic.ratio) == ("부족", 1_500_000, 25.0)
    assert (restorative.status, restorative.shortage, restorative.ratio) == ("미가입", 500_000, 0.0)


def test_samsung_amounts_override_missing_or_incorrect_raw_status():
    prosthetic = normalize_aggregate_values(aggregate(2_000_000, 0, None))
    restorative = normalize_aggregate_values(aggregate(200_000, 370_000, "미가입"))
    assert (prosthetic.status, prosthetic.shortage, prosthetic.ratio) == ("미가입", 2_000_000, 0.0)
    assert (restorative.status, restorative.shortage, restorative.ratio) == ("충분", 0, 185.0)


def test_status_is_not_invented_when_amounts_are_incomplete_or_recommended_is_zero():
    assert normalize_aggregate_status(None, 10, None) == "정보 확인 필요"
    assert normalize_aggregate_status(100, None, "부족") == "부족"
    assert normalize_aggregate_status(0, 500_000, "미가입") == "정보 확인 필요"
    assert normalize_aggregate_values(aggregate(0, 500_000, "미가입")).ratio is None
