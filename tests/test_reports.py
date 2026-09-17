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
    missing_contract = InsuranceContract()
    missing = build_report_data(CustomerInfo(), [], [missing_contract], [])
    assert missing.customer_name == "정보 없음"
    assert missing.contracts == ()
    assert missing_contract.product_name is None  # 원본 계약은 변경하지 않는다.


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
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError as exc:
        pytest.skip(f"Qt system library를 사용할 수 없음: {exc}")
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


def test_samsung_report_status_uses_shared_amount_normalization():
    prosthetic = aggregate("치아보철 치료비", recommended=2_000_000, enrolled=0, status=None)
    restorative = aggregate(
        "치아보존 치료비", category="보존치료", recommended=200_000,
        enrolled=370_000, status="미가입",
    )
    data = build_report_data(CustomerInfo(), [prosthetic, restorative], [], [])
    assert (data.aggregates[0].status, data.aggregates[0].shortage_amount, data.aggregates[0].ratio) == (
        "미가입", 2_000_000, 0.0,
    )
    assert (data.aggregates[1].status, data.aggregates[1].shortage_amount, data.aggregates[1].ratio) == (
        "충분", 0, 185.0,
    )


def test_conflict_warning_is_added_without_removing_validation_issue():
    first = aggregate("치아보철치료비", enrolled=500_000, page=2)
    second = aggregate("치아보철치료비", enrolled=700_000, page=7)
    issue = ValidationIssue("AGGREGATE_AMOUNT_CONFLICT", ValidationSeverity.WARNING, "원본 충돌")
    data = build_report_data(CustomerInfo(), [first, second], [], [], [issue])
    assert len(data.aggregates) == 1
    assert data.aggregate_warnings
    assert data.validation_issues == (issue,)
    html = render_report_html(data)
    assert "원본 자료에서 일부 보장항목의 값이 서로 다르게 확인되어" in html
    for debug_text in ("page 2", "page 7", "가입=None", "후보:", "confidence="):
        assert debug_text not in html


def test_report_contains_only_explicit_dental_product_contracts():
    contracts = [
        InsuranceContract(insurer="삼성화재", product_name="가정종합보험"),
        InsuranceContract(insurer="메리츠화재", product_name="암보험"),
        InsuranceContract(insurer="KDB생명", product_name="연금보험"),
        InsuranceContract(insurer="라이나(에이스)손해보험", product_name="(무)더핏 THE든든한 치아보험 1종(갱신형)"),
    ]
    original = list(contracts)
    data = build_report_data(CustomerInfo(), [], contracts, [])
    assert len(data.contracts) == 1
    assert data.contracts[0].insurer == "라이나(에이스)손해보험"
    assert data.contracts[0].product_name == "(무)더핏 THE든든한 치아보험 1종(갱신형)"
    assert contracts == original and len(contracts) == 4
    assert [page.kind for page in plan_report_pages(data)] == ["summary"]


def test_non_low_linked_dental_rider_can_include_contract_without_name_keyword():
    contract = InsuranceContract(
        insurer="가상손해보험", product_name="튼튼건강보장",
        coverage_period="2025-01-01 ~ 2035-01-01",
    )
    identity = "가상손해보험|튼튼건강보장|2025-01-01 ~ 2035-01-01"
    rider = DentalRider("컴퍼짓레진", contract_identity=identity, confidence=Confidence.MEDIUM)
    assert len(build_report_data(CustomerInfo(), [], [contract], [rider]).contracts) == 1


def test_dynamic_page_plan_omits_empty_contract_and_rider_pages():
    data = build_report_data(CustomerInfo(), [aggregate("치아보철치료비")], [], [])
    pages = plan_report_pages(data)
    assert len(pages) == 1
    assert pages[0].kind == "summary"
    html = render_report_html(data)
    assert "가입된 치아보험" in html
    assert "없음" in html
    assert "세부 치아보장" not in html


def test_comment_is_preserved_escaped_and_omitted_when_blank():
    comment = "보철치료 보장이 부족합니다.\n보험증권 확인이 필요합니다.\n<script>alert(1)</script>"
    data = build_report_data(*sample_data(), comment=comment)
    assert data.comment == comment
    html = render_report_html(data)
    assert "상담 코멘트" in html
    assert "보철치료 보장이 부족합니다.<br>보험증권 확인이 필요합니다." in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "<script>alert(1)</script>" not in html

    blank = render_report_html(build_report_data(*sample_data(), comment="  \n"))
    assert "상담 코멘트" not in blank


def test_no_dental_contract_renders_only_none_not_general_products():
    contracts = [
        InsuranceContract(insurer="삼성화재", product_name="종합보험"),
        InsuranceContract(insurer="메리츠화재", product_name="암보험"),
        InsuranceContract(insurer="KDB생명", product_name="연금보험"),
    ]
    data = build_report_data(CustomerInfo(), [], contracts, [])
    html = render_report_html(data)
    assert data.contracts == ()
    assert "가입된 치아보험" in html and "없음" in html
    assert all(contract.product_name not in html for contract in contracts)
    assert [page.kind for page in plan_report_pages(data)] == ["summary"]


def test_dental_contract_card_does_not_render_none_label():
    data = build_report_data(*sample_data())
    html = render_report_html(data)
    assert "(무)가명 치아보험" in html
    assert '<div class="empty-contracts">없음</div>' not in html


def test_long_comment_gets_dedicated_pages_without_being_dropped():
    comment = "\n".join(f"상담 메모 {index}" for index in range(35))
    data = build_report_data(*sample_data(), comment=comment)
    plans = plan_report_pages(data)
    comment_pages = [page for page in plans if page.comment]
    assert len(comment_pages) >= 2
    assert "\n".join(page.comment for page in comment_pages) == comment


def test_pdf_comment_text_smoke(tmp_path: Path, monkeypatch):
    pytest.importorskip("PySide6", reason="PySide6가 필요한 PDF comment smoke test")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError as exc:
        pytest.skip(f"Qt system library를 사용할 수 없음: {exc}")
    app = QApplication.instance() or QApplication([])
    comment = "보철치료 보장이 부족합니다.\n보험증권 확인이 필요합니다."
    data = build_report_data(*sample_data(), comment=comment)
    assert data.comment == comment
    plans = plan_report_pages(data)
    assert any(page.comment == comment for page in plans)
    html = render_report_html(data)
    assert "상담 코멘트" in html
    assert "보철치료 보장이 부족합니다." in html

    output = export_report_pdf(data, tmp_path / "comment.pdf")
    assert output.exists()
    assert output.stat().st_size > 1000
    assert output.read_bytes().startswith(b"%PDF")
    try:
        import fitz
    except ImportError:
        fitz = None
    if fitz is not None:
        document = fitz.open(output)
        assert document.page_count >= 1
        document.close()
    del app


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
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError as exc:
        pytest.skip(f"Qt system library를 사용할 수 없음: {exc}")
    app = QApplication.instance() or QApplication([])
    data = build_report_data(CustomerInfo(name="가명"), [aggregate("치아보철치료비")], [], [])
    output = export_report_pdf(data, tmp_path / "aggregate-only.pdf")
    document = fitz.open(output)
    assert document.page_count == 1
    assert output.stat().st_size > 0
    document.close()
    del app
