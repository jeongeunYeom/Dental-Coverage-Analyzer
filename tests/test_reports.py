from datetime import date
from pathlib import Path

import pytest

from dental_coverage_analyzer.models import (
    AggregateCoverage, CauseType, CustomerInfo, DentalRider, InsuranceContract, PaymentUnit,
)
from dental_coverage_analyzer.reports import DISCLAIMER, build_report_data, export_report_pdf, render_report_html


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
