from dental_coverage_analyzer.core.pdf.analyzer import PDFAnalysisResult
from dental_coverage_analyzer.models import (
    AggregateCoverage, Confidence, CustomerInfo, DentalRider, PDFDocumentData,
    SourceReference,
)
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


def test_session_exposes_only_canonical_aggregates_and_preserves_raw_candidates(tmp_path):
    from test_canonical_aggregates import actual_conflicting_candidates

    document = PDFDocumentData(tmp_path / "synthetic.pdf", "synthetic.pdf", 0, {}, False, [])
    result = PDFAnalysisResult(document, {}, [], {}, [], [], [])
    result.aggregate_coverages = actual_conflicting_candidates()
    session = AnalysisSession.from_result("synthetic.pdf", result)

    assert len(session.aggregates) == 2
    assert len(session.raw_aggregate_candidates) == 4
    assert len(session.aggregate_conflict_warnings) == 2
    assert session.aggregates[0].source_pages == [6]
    assert session.aggregates[1].enrolled_amount == 0
    assert len(result.to_dict()["aggregate_coverages"]) == 4
    report = build_report_data(
        session.customer, session.raw_aggregate_candidates, session.contracts, session.riders,
        result.validation_issues,
    )
    assert [(item.recommended_amount, item.enrolled_amount) for item in report.aggregates] == [
        (2_000_000, 500_000), (500_000, 0),
    ]
    assert len(report.aggregate_warnings) == 1
