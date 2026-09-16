import pytest

from dental_coverage_analyzer.models import AggregateCoverage, CauseType, DentalRider, SourceReference


def test_aggregate_ratio_only_when_both_amounts_are_known():
    coverage = AggregateCoverage("치아보철치료비", recommended_amount=2_000_000, enrolled_amount=500_000)
    assert coverage.calculate_ratio() == 25.0
    assert AggregateCoverage("치아보존치료비", enrolled_amount=370_000).calculate_ratio() is None


def test_aggregate_and_rider_are_distinct_models():
    aggregate = AggregateCoverage("치아보존치료비", enrolled_amount=370_000)
    rider = DentalRider("컴퍼짓레진", enrolled_amount=90_000, cause_type=CauseType.DISEASE)
    assert type(aggregate) is not type(rider)
    assert aggregate.enrolled_amount == 370_000
    assert rider.enrolled_amount == 90_000


def test_source_page_is_one_based():
    with pytest.raises(ValueError):
        SourceReference(page=0)
