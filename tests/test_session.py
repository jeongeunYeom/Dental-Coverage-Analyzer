from dental_coverage_analyzer.models import AggregateCoverage, CustomerInfo, DentalRider
from dental_coverage_analyzer.reports import build_report_data
from dental_coverage_analyzer.ui.session import AnalysisSession, parse_optional_int


def test_manual_session_add_delete_data_flows_to_report():
    session = AnalysisSession("synthetic.pdf", customer=CustomerInfo(name="가명고객"))
    aggregate = session.add_aggregate()
    aggregate.raw_name = "사용자 추가 보장"
    aggregate.recommended_amount = 1_000_000
    aggregate.enrolled_amount = 500_000
    rider = session.add_rider()
    rider.raw_name = "사용자 추가 담보"
    rider.enrolled_amount = 30_000
    data = build_report_data(session.customer, session.aggregates, session.contracts, session.riders)
    assert data.aggregates[0].name == "사용자 추가 보장"
    assert data.riders[0].name == "사용자 추가 담보"
    assert parse_optional_int("1,500,000원") == 1_500_000
    assert parse_optional_int("정보 없음") is None
