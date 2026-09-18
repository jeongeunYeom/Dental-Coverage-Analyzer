from datetime import date

from dental_coverage_analyzer.branding import BrandingSettings
from dental_coverage_analyzer.reports import render_report_html
from dental_coverage_analyzer.reports.view_models import ReportData


def test_html_report_contains_branding_and_escapes_footer():
    branding = BrandingSettings("가상 컨설팅", "홍길동", "010-1234-5678", footer_text="<문의>", primary_color="#123ABC")
    html = render_report_html(ReportData("가명고객", date(2026, 9, 18), branding=branding))
    assert all(value in html for value in ("가상 컨설팅", "홍길동", "010-1234-5678", "#123ABC"))
    assert "&lt;문의&gt;" in html and "<문의>" not in html


def test_default_branding_does_not_render_empty_contact_card():
    html = render_report_html(ReportData("가명고객", date(2026, 9, 18)))
    assert 'class="brand-contact"' not in html


def test_branded_pdf_smoke(tmp_path):
    pytest = __import__("pytest")
    pytest.importorskip("PySide6")
    from dental_coverage_analyzer.reports import export_report_pdf
    data = ReportData("가명고객", date(2026, 9, 18), branding=BrandingSettings("가상 컨설팅", "홍길동"))
    output = export_report_pdf(data, tmp_path / "branded.pdf")
    assert output.read_bytes().startswith(b"%PDF")
    assert output.stat().st_size > 1000
