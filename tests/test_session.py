from dental_coverage_analyzer.core.pdf.analyzer import PDFAnalysisResult
from dental_coverage_analyzer.models import (
    AggregateCoverage, Confidence, CustomerInfo, DentalRider, PDFDocumentData,
    SourceReference,
)
from dental_coverage_analyzer.reports import build_report_data
from dental_coverage_analyzer.ui.session import AnalysisSession, parse_optional_date, parse_optional_int


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


def test_session_comment_is_passed_to_report_without_changes():
    comment = "보철치료 보장이 부족합니다.\n보험증권 확인이 필요합니다."
    session = AnalysisSession("synthetic.pdf", customer=CustomerInfo(name="가명고객"), comment=comment)
    data = build_report_data(
        session.customer, session.aggregates, session.contracts, session.riders,
        comment=session.comment,
    )
    assert data.comment == comment


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


def test_deleting_canonical_aggregate_removes_its_entire_raw_group(tmp_path):
    from dental_coverage_analyzer.ui.project_store import load_project, save_project
    from test_canonical_aggregates import actual_conflicting_candidates

    document = PDFDocumentData(tmp_path / "synthetic.pdf", "synthetic.pdf", 0, {}, False, [])
    result = PDFAnalysisResult(document, {}, [], {}, [], [], [])
    result.aggregate_coverages = actual_conflicting_candidates()
    session = AnalysisSession.from_result("synthetic.pdf", result)
    session.delete_aggregate_group(session.aggregates[0])

    assert [item.category for item in session.aggregates] == ["보존치료"]
    assert {item.category for item in session.raw_aggregate_candidates} == {"보존치료"}
    report = build_report_data(
        session.customer, session.raw_aggregate_candidates, session.contracts, session.riders,
    )
    assert [item.category for item in report.aggregates] == ["보존치료"]

    destination = tmp_path / "deleted-group.dca"
    save_project(session, destination)
    restored = load_project(destination).session
    assert [item.category for item in restored.aggregates] == ["보존치료"]
    assert {item.category for item in restored.raw_aggregate_candidates} == {"보존치료"}


def test_optional_enrollment_date_parser():
    assert parse_optional_date("2025-02-03").isoformat() == "2025-02-03"
    assert parse_optional_date("정보 없음") is None
