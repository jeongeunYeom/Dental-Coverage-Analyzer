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
    progress = ""
    if item.ratio is not None:
        width = min(max(item.ratio, 0), 100)
        progress = f'<div class="progress"><div class="progress-fill" style="width:{width:.1f}%;background:{color}"></div></div>'
    ratio = f"{item.ratio:.0f}%" if item.ratio is not None else "정보 확인 필요"
    status_color = "#EF6A75" if item.needs_review or item.status in {"부족", "미가입"} else "#3DBB8A"
    return f"""<td class="summary-card">
      <span class="badge" style="background:{color}">{escape(item.category)}</span>
      <div class="coverage-name">{escape(item.name)}</div>
      <div class="main-amount">{format_money(item.enrolled_amount)}</div><div class="amount-label">현재 가입금액</div>
      <div class="sub-amount">권장&nbsp; {format_money(item.recommended_amount)}<br>부족&nbsp; {format_money(item.shortage_amount)}</div>
      <div class="ratio" style="color:{color}">{ratio}</div><div class="amount-label">현재 보장률</div>{progress}
      <b style="color:{status_color}">{escape(item.status or '정보 확인 필요')}</b>
    </td>"""


def _aggregate_grid(items) -> str:
    cards = [_aggregate_card(item) for item in items]
    rows = [f'<table class="grid"><tr>{"".join(cards[index:index + 2])}</tr></table>' for index in range(0, len(cards), 2)]
    return "".join(rows) or '<div class="summary-card secondary">전체 치아보장 정보를 확인하지 못했습니다.</div>'


def _contracts(items) -> str:
    return "".join(
        f'<div class="contract-card"><span class="badge" style="background:#EFEEFF;color:#625EF5">{escape(item.insurer or "보험사 정보 없음")}</span>'
        f'<div class="product-name">{escape(item.product_name or "상품명 정보 없음")}</div>'
        f'<span class="secondary">보험기간 {escape(item.coverage_period or "정보 없음")} · 월 보험료 {format_money(item.monthly_premium)}</span></div>'
        for item in items
    )


def _comment(value: str) -> str:
    if not value.strip():
        return ""
    safe_text = escape(value).replace("\n", "<br>")
    return f'<div class="comment-card"><h2>상담 코멘트</h2><div class="comment-text">{safe_text}</div></div>'


def _riders(items) -> str:
    grouped = defaultdict(list)
    for rider in items:
        grouped[rider.category].append(rider)
    sections = []
    ordered = [*CATEGORY_COLORS, *(name for name in grouped if name not in CATEGORY_COLORS)]
    for category in ordered:
        if not grouped.get(category):
            continue
        rows = "".join(
            f'<table class="rider-row"><tr><td><div class="rider-name">{escape(item.name)}</div>'
            f'<span class="secondary">{escape(item.category)} · {escape(item.cause_type)} · {escape(item.payment_unit)}</span></td>'
            f'<td class="rider-amount">{format_money(item.amount)}</td></tr></table>' for item in grouped[category]
        )
        sections.append(f'<div class="category-title" style="background:{CATEGORY_COLORS.get(category, DEFAULT_COLOR)}">{escape(category)}</div>{rows}')
    return "".join(sections)


def render_report_html(data: ReportData) -> str:
    template = load_text_resource("report/template.html")
    css = load_text_resource("report/report.css")
    hero = (
        '<div class="hero"><div class="eyebrow">DENTAL COVERAGE ANALYSIS</div>'
        '<h1>치아보험 보장분석표</h1>'
        f'<div class="meta"><b>고객명</b>&nbsp; {escape(data.customer_name)} &nbsp;&nbsp;·&nbsp;&nbsp; '
        f'<b>분석일</b>&nbsp; {data.analysis_date.isoformat()}</div></div>'
    )
    body = [f'<section class="page">{hero}<h2>전체 치아보장 요약</h2>{_aggregate_grid(data.aggregates)}']
    body.extend(f'<div class="warning">⚠ {escape(warning)}</div>' for warning in data.aggregate_warnings)
    attach_contracts = bool(data.contracts) and len(data.contracts) <= 2 and len(data.aggregates) <= 2 and len(data.aggregate_warnings) <= 1
    if attach_contracts:
        body.append(f'<h2>가입된 치아보험</h2>{_contracts(data.contracts)}')
    elif not data.contracts:
        body.append('<h2>가입된 치아보험</h2><div class="empty-contracts">없음</div>')
    body.append('</section>')
    if data.contracts and not attach_contracts:
        body.append(f'<div class="page-break"></div><section class="page"><h1>가입된 치아보험</h1>{_contracts(data.contracts)}</section>')
    if data.riders:
        body.append(f'<div class="page-break"></div><section class="page"><h1>세부 치아보장</h1><p class="secondary">지급조건과 지급단위가 다른 담보는 합산하지 않았습니다.</p>{_riders(data.riders)}</section>')
    body.append(_comment(data.comment))
    body.append(f'<div class="disclaimer">{escape(DISCLAIMER)}<br><b>서로 다른 지급단위의 세부 담보는 단순 합산하지 않았습니다.</b></div>')
    return template.replace("{{CSS}}", css).replace("{{BODY}}", "".join(body))


def export_report_pdf(data: ReportData, output: str | Path) -> Path:
    """최종 PDF는 QPdfWriter/QPainter renderer가 생성한다."""
    from .pdf_renderer import export_report_pdf as _export
    return _export(data, output)
