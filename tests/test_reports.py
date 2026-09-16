from datetime import date
from pathlib import Path

import pytest

from dental_coverage_analyzer.models import (
    AggregateCoverage, CauseType, Confidence, CustomerInfo, DentalRider, InsuranceContract,
    PaymentUnit, SourceReference, ValidationIssue, ValidationSeverity,
)
from dental_coverage_analyzer.reports import (
    DISCLAIMER, build_report_data, export_report_pdf, plan_report_pages, render_report_html,
    select_representative_aggregates,
)


def sample_data():
    customer = CustomerInfo(name="가명고객", analysis_date=date(2026, 9, 16))
    aggregates = [AggregateCoverage(
        "치아보철치료비", category="보철치료", recommended_amount=2_000_000,
        enrolled_amount=500_000, normalized_shortage=1_500_000, status="부족",
    )]
    contracts = [InsuranceContract(
        insurer="합성손해보험", product_name="(무)가명 치아보험",
        coverage_period="2025-01-01 ~ 2060-01-01", monthly_premium=17_610,
    )]
    riders = [DentalRider(
        "컴퍼짓레진", category="보존치료", insurer="합성손해보험",
        product_name="(무)가명 치아보험", enrolled_amount=90_000,
        cause_type=CauseType.DISEASE, payment_unit=PaymentUnit.PER_TOOTH,
    )]
    return customer, aggregates, contracts, riders


def test_report_data_is_decoupled_and_preserves_no_guess_values():
    customer, aggregates, contracts, riders = sample_data()
    data = build_report_data(customer, aggregates, contracts, riders)
    assert data.customer_name == "가명고객"
    assert data.aggregates[0].ratio == 25.0
    assert data.riders[0].amount == 90_000
    assert data.contracts[0].monthly_premium == 17_610
    missing = build_report_data(CustomerInfo(), [], [InsuranceContract()], [])
    assert missing.customer_name == "정보 없음"
    assert missing.contracts[0].insurer is None


def test_manual_edits_are_reflected_when_report_data_is_rebuilt():
    customer, aggregates, contracts, riders = sample_data()
    aggregates[0].enrolled_amount = 700_000
    riders[0].raw_name = "사용자 수정 담보명"
    contracts[0].insurer = "사용자 수정 보험사"
    data = build_report_data(customer, aggregates, contracts, riders)
    assert data.aggregates[0].enrolled_amount == 700_000
    assert data.aggregates[0].ratio == 35.0
    assert data.riders[0].name == "사용자 수정 담보명"
    assert data.contracts[0].insurer == "사용자 수정 보험사"


def test_html_report_contains_cards_colors_disclaimer_and_no_rider_total():
    html = render_report_html(build_report_data(*sample_data()))
    assert "치아보험 보장분석표" in html
    assert "#625EF5" in html and "#43B7E8" in html
    assert "25%" in html
    assert "컴퍼짓레진" in html and "90,000원" in html
    assert DISCLAIMER in html
    assert "서로 다른 지급단위의 세부 담보는 단순 합산하지 않았습니다" in html
    assert "총 치아보험금" not in html


def test_pdf_export_smoke(tmp_path: Path, monkeypatch):
    pytest.importorskip("PySide6", reason="PySide6가 필요한 PDF 출력 smoke test")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    output = export_report_pdf(build_report_data(*sample_data()), tmp_path / "report.pdf")
    assert output.read_bytes().startswith(b"%PDF")
    assert output.stat().st_size > 1000
    del app


def aggregate(name, *, category="보철치료", confidence=Confidence.MEDIUM, recommended=2_000_000, enrolled=500_000, page=1, status="부족"):
    return AggregateCoverage(
        name, category=category, recommended_amount=recommended, enrolled_amount=enrolled,
        normalized_shortage=max(recommended - enrolled, 0) if recommended is not None and enrolled is not None and recommended > 0 else None,
        status=status, confidence=confidence, source_pages=[page],
        representative_source=SourceReference(page, raw_text=f"{name} synthetic source"),
    )


def test_logically_valid_complete_aggregate_beats_high_confidence_incomplete_candidate():
    high_incomplete = aggregate("고신뢰 보철", confidence=Confidence.HIGH, enrolled=None, page=4)
    medium_complete = aggregate("완전한 보철", confidence=Confidence.MEDIUM, page=1)
    selected, warnings = select_representative_aggregates([medium_complete, high_incomplete])
    assert selected == [medium_complete]
    assert warnings


def test_complete_aggregate_wins_over_incomplete_at_same_confidence():
    incomplete = aggregate("불완전 보철", enrolled=None, page=1)
    complete = aggregate("완전 보철", page=8)
    selected, _ = select_representative_aggregates([incomplete, complete])
    assert selected == [complete]


def test_invalid_zero_recommendation_is_not_calculated_in_report():
    invalid = aggregate("비정상 보존", category="보존치료", recommended=0, enrolled=500_000, status="미가입")
    data = build_report_data(CustomerInfo(name="가명"), [invalid], [], [])
    assert data.aggregates[0].recommended_amount is None
    assert data.aggregates[0].ratio is None
    assert data.aggregates[0].status == "정보 확인 필요"


def test_conflict_warning_is_added_without_removing_validation_issue():
    first = aggregate("치아보철치료비", enrolled=500_000, page=2)
    second = aggregate("치아보철치료비", enrolled=700_000, page=7)
    issue = ValidationIssue("AGGREGATE_AMOUNT_CONFLICT", ValidationSeverity.WARNING, "원본 충돌")
    data = build_report_data(CustomerInfo(), [first, second], [], [], [issue])
    assert len(data.aggregates) == 1
    assert data.aggregate_warnings
    assert data.validation_issues == (issue,)


def test_dynamic_page_plan_omits_empty_contract_and_rider_pages():
    data = build_report_data(CustomerInfo(), [aggregate("치아보철치료비")], [], [])
    pages = plan_report_pages(data)
    assert len(pages) == 1
    assert pages[0].kind == "summary"
    html = render_report_html(data)
    assert "가입된 치아보험" not in html
    assert "세부 치아보장" not in html


def test_small_contract_list_is_attached_to_summary_and_riders_add_only_real_page():
    _, aggregates, contracts, riders = sample_data()
    no_riders = build_report_data(CustomerInfo(), aggregates, contracts, [])
    assert [page.kind for page in plan_report_pages(no_riders)] == ["summary"]
    with_riders = build_report_data(CustomerInfo(), aggregates, contracts, riders)
    assert [page.kind for page in plan_report_pages(with_riders)] == ["summary", "riders"]


def test_aggregate_only_qpdfwriter_output_is_one_page(tmp_path: Path, monkeypatch):
    pytest.importorskip("PySide6", reason="PySide6가 필요한 QPdfWriter smoke test")
    fitz = pytest.importorskip("fitz", reason="PDF page count 확인에 PyMuPDF 필요")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    data = build_report_data(CustomerInfo(name="가명"), [aggregate("치아보철치료비")], [], [])
    output = export_report_pdf(data, tmp_path / "aggregate-only.pdf")
    document = fitz.open(output)
    assert document.page_count == 1
    assert output.stat().st_size > 0
    document.close()
    del app
