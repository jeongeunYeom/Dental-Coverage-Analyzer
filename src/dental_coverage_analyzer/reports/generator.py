from __future__ import annotations

from collections import defaultdict
from html import escape
from pathlib import Path

from dental_coverage_analyzer.core.resources import load_text_resource

from .theme import CATEGORY_COLORS, DEFAULT_COLOR
from .view_models import ReportData


DISCLAIMER = (
    "본 자료는 업로드된 보험 보장분석 자료를 기반으로 정리한 참고용 자료입니다. "
    "실제 보험금 지급 여부 및 금액은 보험계약, 약관, 가입 조건 및 보험사의 심사 결과에 따라 "
    "달라질 수 있습니다. 상세 내용은 해당 보험증권 및 약관을 반드시 확인하시기 바랍니다."
)


def format_money(value: int | None) -> str:
    return "정보 없음" if value is None else f"{value:,}원"


def _aggregate_card(item) -> str:
    color = CATEGORY_COLORS.get(item.category, DEFAULT_COLOR)
    ratio = item.ratio
    progress = ""
    if ratio is not None:
        width = min(max(ratio, 0), 100)
        progress = (
            f'<div class="progress"><div class="progress-fill" '
            f'style="width:{width:.1f}%;background:{color}"></div></div>'
        )
    return f"""<div class="card">
      <div class="card-title" style="color:{color}">{escape(item.name)}</div>
      <table class="amount-grid"><tr>
      <td><div class="label">가입금액</div><div class="value">{format_money(item.enrolled_amount)}</div></td>
      <td><div class="label">권장금액</div><div class="value">{format_money(item.recommended_amount)}</div></td>
      <td><div class="label">부족금액 / 보장률</div><div class="value">{format_money(item.shortage_amount)} / {f'{ratio:.0f}%' if ratio is not None else '정보 없음'}</div></td>
      </tr></table>{progress}<span class="badge" style="background:{color}">{escape(item.status or '확인 필요')}</span>
    </div>"""


def render_report_html(data: ReportData) -> str:
    template = load_text_resource("report/template.html")
    css = load_text_resource("report/report.css")
    aggregate_cards = "".join(_aggregate_card(item) for item in data.aggregates) or '<p class="muted">확인된 전체 치아보장이 없습니다.</p>'
    contracts = "".join(
        f'<div class="card contract"><div class="card-title">{escape(item.product_name or "정보 없음")}</div>'
        f'<b>{escape(item.insurer or "정보 없음")}</b><br>'
        f'보험기간 {escape(item.coverage_period or "정보 없음")} · 월보험료 {format_money(item.monthly_premium)}</div>'
        for item in data.contracts
    ) or '<p class="muted">확인된 치아보험 상품이 없습니다.</p>'
    grouped = defaultdict(list)
    for rider in data.riders:
        grouped[rider.category].append(rider)
    sections = []
    ordered_categories = [*CATEGORY_COLORS, *(name for name in grouped if name not in CATEGORY_COLORS)]
    for category in ordered_categories:
        items = grouped.get(category, [])
        if not items:
            continue
        rows = "".join(
            f'<table class="rider-row"><tr><td><b>{escape(item.name)}</b><br><span class="muted">'
            f'{escape(item.insurer or "정보 없음")} · {escape(item.cause_type)} · {escape(item.payment_unit)}</span></td>'
            f'<td class="rider-amount">{format_money(item.amount)}</td></tr></table>' for item in items
        )
        sections.append(f'<div class="category-title" style="background:{CATEGORY_COLORS.get(category, DEFAULT_COLOR)}">{escape(category)}</div>{rows}')
    riders = "".join(sections) or '<p class="muted">확인된 세부 치아담보가 없습니다.</p>'
    replacements = {
        "{{CSS}}": css, "{{CUSTOMER_NAME}}": escape(data.customer_name),
        "{{ANALYSIS_DATE}}": data.analysis_date.isoformat(), "{{AGGREGATE_CARDS}}": aggregate_cards,
        "{{CONTRACT_CARDS}}": contracts, "{{RIDER_SECTIONS}}": riders,
        "{{DISCLAIMER}}": DISCLAIMER,
    }
    for token, value in replacements.items():
        template = template.replace(token, value)
    return template


def export_report_pdf(data: ReportData, output: str | Path) -> Path:
    """PySide6 QTextDocument/QPrinter로 외부 executable 없이 PDF를 생성한다."""
    from PySide6.QtCore import QMarginsF
    from PySide6.QtGui import QPageLayout, QPageSize, QTextDocument
    from PySide6.QtPrintSupport import QPrinter

    path = Path(output).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    printer.setOutputFileName(str(path))
    printer.setPageLayout(QPageLayout(QPageSize(QPageSize.PageSizeId.A4), QPageLayout.Orientation.Portrait, QMarginsF(15, 15, 15, 15)))
    document = QTextDocument()
    document.setHtml(render_report_html(data))
    document.print_(printer)
    if not path.is_file() or path.stat().st_size == 0:
        raise RuntimeError("PDF 보고서를 생성하지 못했습니다")
    return path
