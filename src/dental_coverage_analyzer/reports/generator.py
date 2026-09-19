from __future__ import annotations

from collections import defaultdict
from html import escape
from pathlib import Path

from dental_coverage_analyzer.core.resources import load_text_resource

from .theme import (
    CATEGORY_COLORS, DEFAULT_COLOR, REPORT_COLORS, SEVERITY_STYLES, report_primary_color,
    status_style,
)
from .view_models import ReportAggregate, ReportData


DISCLAIMER = (
    "본 자료는 업로드된 보험 보장분석 자료를 기반으로 정리한 참고용 자료입니다. "
    "실제 보험금 지급 여부 및 금액은 보험계약, 약관, 가입 조건 및 보험사의 심사 결과에 따라 "
    "달라질 수 있습니다. 상세 내용은 해당 보험증권 및 약관을 반드시 확인하시기 바랍니다."
)


def format_money(value: int | None) -> str:
    return "정보 없음" if value is None else f"{value:,}원"


def _format_ratio(value: float | None) -> str:
    return "정보 확인 필요" if value is None else f"{value:.0f}%"


def _badge(text: str, *, status: str | None = None, needs_review: bool = False) -> str:
    bg, fg = status_style(status or text, needs_review=needs_review)
    return f'<span class="status-badge" style="background:{bg};color:{fg}">{escape(text)}</span>'


def _empty_state(title: str, description: str) -> str:
    return (
        '<div class="empty-state">'
        f'<div class="empty-title">{escape(title)}</div>'
        f'<div class="empty-copy">{escape(description)}</div>'
        '</div>'
    )


def _kpi_items(data: ReportData) -> tuple[tuple[str, str, str], ...]:
    missing = sum(1 for item in data.aggregates if item.status == "미가입")
    shortage = sum(1 for item in data.aggregates if item.status == "부족")
    review = sum(
        1 for item in data.aggregates
        if item.needs_review or item.status in {"확인 필요", "정보 확인 필요"} or item.ratio is None
    )
    review += len(data.validation_issues) + len(data.aggregate_warnings)
    return (
        ("가입 상품", f"{len(data.contracts)}개", "원본에서 확인된 치아보험"),
        ("세부 담보", f"{len(data.riders)}개", "지급조건별 치아담보"),
        ("부족 항목", f"{shortage}개", "권장금액 대비 부족"),
        ("미가입 항목", f"{missing}개", "가입금액 0원 또는 미확인"),
        ("확인 필요", f"{review}개", "검토가 필요한 항목"),
    )


def _kpi_cards(data: ReportData) -> str:
    return "".join(
        '<div class="kpi-card">'
        f'<div class="kpi-label">{escape(label)}</div>'
        f'<div class="kpi-value">{escape(value)}</div>'
        f'<div class="kpi-caption">{escape(caption)}</div>'
        '</div>'
        for label, value, caption in _kpi_items(data)
    )


def _priority_items(data: ReportData) -> tuple[ReportAggregate, ...]:
    priority = [item for item in data.aggregates if item.status in {"미가입", "부족"} or item.needs_review]
    priority.sort(key=lambda item: (
        0 if item.status == "미가입" else 1 if item.status == "부족" else 2,
        -(item.shortage_amount or 0),
        item.name,
    ))
    return tuple(priority[:3])


def _insight_summary(data: ReportData) -> str:
    priority = _priority_items(data)
    sufficient = [item for item in data.aggregates if item.status == "충분"][:3]
    missing = [item for item in data.aggregates if item.status == "미가입"][:3]

    if priority:
        priority_items = "".join(
            f'<li>{escape(item.name)} {escape(item.status or "확인 필요")} - 부족금액 {format_money(item.shortage_amount)}</li>'
            for item in priority
        )
    else:
        priority_items = "<li>현재 표시된 보장 요약에서 즉시 보완이 필요한 항목은 확인되지 않았습니다.</li>"

    sufficient_items = "".join(f"<li>{escape(item.name)}</li>" for item in sufficient) or "<li>충분으로 분류된 항목이 없습니다.</li>"
    missing_items = "".join(f"<li>{escape(item.name)}</li>" for item in missing) or "<li>미가입으로 분류된 항목이 없습니다.</li>"
    return f"""
    <section class="insight-panel">
      <div class="insight-column"><h3>보완 추천</h3><ul>{priority_items}</ul></div>
      <div class="insight-column"><h3>충분한 항목</h3><ul>{sufficient_items}</ul></div>
      <div class="insight-column"><h3>미가입 항목</h3><ul>{missing_items}</ul></div>
    </section>
    """


def _aggregate_card(item: ReportAggregate) -> str:
    color = CATEGORY_COLORS.get(item.category, DEFAULT_COLOR)
    progress = ""
    if item.ratio is not None:
        width = min(max(item.ratio, 0), 100)
        progress = f'<div class="progress"><div class="progress-fill" style="width:{width:.1f}%;background:{color}"></div></div>'
    status = item.status or "정보 확인 필요"
    source = f"원본 {item.source_page}페이지" if item.source_page else "원본 페이지 정보 없음"
    return f"""<article class="summary-card">
      <div class="card-head"><span class="category-chip" style="background:{color}">{escape(item.category)}</span>{_badge(status, status=status, needs_review=item.needs_review)}</div>
      <div class="coverage-name">{escape(item.name)}</div>
      <div class="metrics">
        <div><span>가입금액</span><b>{format_money(item.enrolled_amount)}</b></div>
        <div><span>권장금액</span><b>{format_money(item.recommended_amount)}</b></div>
        <div><span>부족금액</span><b>{format_money(item.shortage_amount)}</b></div>
        <div><span>보장률</span><b>{_format_ratio(item.ratio)}</b></div>
      </div>
      {progress}
      <div class="source-note">{escape(source)} · 신뢰도 {escape(item.confidence)}</div>
    </article>"""


def _aggregate_grid(items: tuple[ReportAggregate, ...]) -> str:
    if not items:
        return _empty_state("전체 치아보장 정보를 확인하지 못했습니다", "원본 문서에서 표시 가능한 치아 보장 요약 항목이 없습니다.")
    return '<div class="summary-grid">' + "".join(_aggregate_card(item) for item in items) + "</div>"


def _contracts(data: ReportData) -> str:
    if not data.contracts:
        return _empty_state("가입된 치아보험이 없습니다", "원본 문서에서 확인 가능한 치아보험 상품이 없습니다.")
    return "".join(
        '<article class="contract-card">'
        f'<div class="contract-insurer">{escape(item.insurer or "보험사 정보 없음")}</div>'
        f'<div class="product-name">{escape(item.product_name or "상품명 정보 없음")}</div>'
        '<div class="contract-meta">'
        f'<span>보험기간 {escape(item.coverage_period or "정보 없음")}</span>'
        f'<span>월 보험료 {format_money(item.monthly_premium)}</span>'
        '</div></article>'
        for item in data.contracts
    )


def _comment(value: str) -> str:
    if not value.strip():
        return _empty_state("상담 코멘트가 없습니다", "보고서에 표시할 별도 상담 코멘트가 입력되지 않았습니다.")
    safe_text = escape(value).replace("\n", "<br>")
    return f'<div class="comment-card"><h2>상담 코멘트</h2><div class="comment-text">{safe_text}</div></div>'


def _riders(data: ReportData) -> str:
    if not data.riders:
        return _empty_state("세부 치아담보가 없습니다", "원본 문서에서 확인 가능한 세부 치아담보가 없습니다.")
    grouped = defaultdict(list)
    for rider in data.riders:
        grouped[rider.category].append(rider)
    ordered = [*CATEGORY_COLORS, *(name for name in grouped if name not in CATEGORY_COLORS)]
    sections = []
    for category in ordered:
        if not grouped.get(category):
            continue
        rows = "".join(
            "<tr>"
            f"<td>{escape(item.name)}<span>{escape(item.insurer or '보험사 정보 없음')} · {escape(item.product_name or '상품명 정보 없음')}</span></td>"
            f"<td class=\"amount\">{format_money(item.amount)}</td>"
            f"<td>{escape(item.cause_type)}</td>"
            f"<td>{escape(item.payment_unit)}</td>"
            "</tr>"
            for item in grouped[category]
        )
        sections.append(
            f'<section class="rider-group"><div class="category-title" style="border-color:{CATEGORY_COLORS.get(category, DEFAULT_COLOR)}">{escape(category)}</div>'
            '<table class="rider-table"><thead><tr><th>담보명</th><th>가입금액</th><th>구분</th><th>지급단위</th></tr></thead>'
            f"<tbody>{rows}</tbody></table></section>"
        )
    return "".join(sections)


def _issues(data: ReportData) -> str:
    items = []
    for issue in data.validation_issues:
        bg, fg, label = SEVERITY_STYLES.get(issue.severity.value, SEVERITY_STYLES["INFO"])
        pages = ", ".join(map(str, issue.page_numbers))
        suffix = f" · 원본 {pages}페이지" if pages else ""
        items.append(
            f'<li><span style="background:{bg};color:{fg}">{escape(label)}</span>'
            f'{escape(issue.message)}{escape(suffix)}</li>'
        )
    for warning in data.aggregate_warnings:
        items.append(f'<li><span style="background:{REPORT_COLORS["warning_bg"]};color:#9A6700">주의</span>{escape(warning)}</li>')
    if not items:
        return _empty_state("확인 필요 항목이 없습니다", "자동 분석 결과에서 별도 확인이 필요한 항목이 표시되지 않았습니다.")
    return '<ul class="issue-list">' + "".join(items) + "</ul>"


def _brand_contact(data: ReportData, primary: str) -> str:
    brand = data.branding
    contacts = " · ".join(filter(None, (
        brand.company_name,
        f"담당자 {brand.consultant_name}" if brand.consultant_name else "",
        brand.phone,
        brand.email,
    )))
    blocks = []
    if contacts:
        blocks.append(f'<div class="brand-contact" style="border-left-color:{primary}">{escape(contacts)}</div>')
    if brand.footer_text.strip():
        footer = escape(brand.footer_text).replace("\n", "<br>")
        blocks.append(f'<div class="brand-footer">{footer}</div>')
    return "".join(blocks)


def render_report_html(data: ReportData) -> str:
    template = load_text_resource("report/template.html")
    css = load_text_resource("report/report.css")
    brand = data.branding
    primary = escape(report_primary_color(brand), quote=True)
    logo = ""
    if brand.logo_path and Path(brand.logo_path).is_file():
        logo = f'<img class="brand-logo" src="{escape(Path(brand.logo_path).resolve().as_uri(), quote=True)}">'
    company = f'<div class="brand-name">{escape(brand.company_name)}</div>' if brand.company_name else ""
    brand_line = " · ".join(filter(None, (
        f"담당자 {brand.consultant_name}" if brand.consultant_name else "",
        brand.phone,
        brand.email,
    )))
    brand_line_html = f'<div class="brand-line">{escape(brand_line)}</div>' if brand_line else ""
    hero = (
        f'<header class="hero" style="border-top-color:{primary}">{logo}{company}'
        f'<div class="eyebrow" style="color:{primary}">DENTAL COVERAGE ANALYSIS</div>'
        '<h1>치아보험 보장분석표</h1>'
        '<p>고객님의 치아 관련 보장 현황과 보완 필요 항목을 정리한 보고서</p>'
        f'<div class="meta"><b>고객명</b> {escape(data.customer_name)} <span>·</span> '
        f'<b>분석일</b> {data.analysis_date.isoformat()} <span>·</span> '
        f'<b>치아보험 상품</b> {len(data.contracts)}개</div>'
        f'{brand_line_html}</header>'
    )

    body = [
        '<section class="page">',
        hero,
        f'<section class="kpi-grid">{_kpi_cards(data)}</section>',
        '<h2>핵심 결과 요약</h2>',
        _insight_summary(data),
        '<h2>전체 보장 요약</h2>',
        _aggregate_grid(data.aggregates),
        '<h2>가입된 치아보험 상품</h2>',
        _contracts(data),
        '<div class="page-break"></div>',
        '<h2>세부 치아담보</h2>',
        _riders(data),
        '<h2>확인 필요 항목</h2>',
        _issues(data),
        _comment(data.comment),
        _brand_contact(data, primary),
        f'<footer class="report-footer"><span>{escape(DISCLAIMER)} 서로 다른 지급단위의 세부 담보는 단순 합산하지 않았습니다.</span><b>생성일 {data.analysis_date.isoformat()}</b></footer>',
        '</section>',
    ]
    return template.replace("{{CSS}}", css).replace("{{BODY}}", "".join(body))


def export_report_pdf(data: ReportData, output: str | Path) -> Path:
    """최종 PDF는 QPdfWriter/QPainter renderer가 생성한다."""
    from .pdf_renderer import export_report_pdf as _export
    return _export(data, output)
