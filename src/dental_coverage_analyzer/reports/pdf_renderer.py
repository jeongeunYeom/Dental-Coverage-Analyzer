from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
import textwrap
from pathlib import Path

from dental_coverage_analyzer.models import ValidationIssue

from .generator import DISCLAIMER, format_money
from .theme import (
    CATEGORY_COLORS, DEFAULT_COLOR, REPORT_COLORS, SEVERITY_STYLES, report_primary_color,
    status_style,
)
from .view_models import ReportAggregate, ReportContract, ReportData, ReportRider


@dataclass(frozen=True, slots=True)
class ReportPagePlan:
    kind: str
    aggregates: tuple[ReportAggregate, ...] = field(default_factory=tuple)
    contracts: tuple[ReportContract, ...] = field(default_factory=tuple)
    riders: tuple[ReportRider, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)
    issues: tuple[ValidationIssue, ...] = field(default_factory=tuple)
    comment: str = ""


def _comment_lines(comment: str, width: int = 62) -> list[str]:
    lines: list[str] = []
    for paragraph in comment.split("\n"):
        lines.extend(textwrap.wrap(
            paragraph, width=width, replace_whitespace=False,
            drop_whitespace=False, break_long_words=True,
        ) or [""])
    return lines


def _comment_chunks(comment: str, lines_per_page: int = 22) -> tuple[str, ...]:
    lines = _comment_lines(comment)
    return tuple("\n".join(lines[start:start + lines_per_page]) for start in range(0, len(lines), lines_per_page))


def _grouped_riders(riders: tuple[ReportRider, ...]) -> tuple[ReportRider, ...]:
    grouped = defaultdict(list)
    for rider in riders:
        grouped[rider.category].append(rider)
    ordered = [*CATEGORY_COLORS, *(name for name in grouped if name not in CATEGORY_COLORS)]
    return tuple(rider for category in ordered for rider in grouped.get(category, ()))


def plan_report_pages(data: ReportData) -> tuple[ReportPagePlan, ...]:
    """Create page-sized chunks without changing report data semantics."""
    attached_contracts = (
        data.contracts
        if len(data.contracts) <= 2 and len(data.aggregates) <= 2 and len(data.aggregate_warnings) <= 1
        else ()
    )
    pages: list[ReportPagePlan] = [ReportPagePlan(
        "summary", data.aggregates[:4], attached_contracts, warnings=data.aggregate_warnings,
    )]
    if len(data.aggregates) > 4:
        for start in range(4, len(data.aggregates), 4):
            pages.append(ReportPagePlan("aggregates", data.aggregates[start:start + 4]))
    if data.contracts and not attached_contracts:
        for start in range(0, len(data.contracts), 5):
            pages.append(ReportPagePlan("contracts", contracts=data.contracts[start:start + 5]))
    grouped_riders = _grouped_riders(data.riders)
    if grouped_riders:
        for start in range(0, len(grouped_riders), 9):
            pages.append(ReportPagePlan("riders", riders=grouped_riders[start:start + 9]))
    if data.validation_issues:
        for start in range(0, len(data.validation_issues), 8):
            pages.append(ReportPagePlan("issues", issues=data.validation_issues[start:start + 8]))
    if data.comment.strip():
        has_branding_footer = data.branding.has_contact_details or bool(data.branding.footer_text.strip())
        can_attach = (
            pages[-1].kind == "summary" and len(data.aggregates) <= 2
            and len(data.aggregate_warnings) <= 1 and len(data.contracts) <= 2
            and len(_comment_lines(data.comment)) <= 10
            and not has_branding_footer
        )
        if can_attach:
            pages[-1] = dataclass_replace(pages[-1], comment=data.comment)
        else:
            lines_per_page = 14 if has_branding_footer else 22
            pages.extend(ReportPagePlan("comment", comment=chunk) for chunk in _comment_chunks(data.comment, lines_per_page))
    return tuple(pages)


def dataclass_replace(plan: ReportPagePlan, **changes) -> ReportPagePlan:
    values = {
        "kind": plan.kind,
        "aggregates": plan.aggregates,
        "contracts": plan.contracts,
        "riders": plan.riders,
        "warnings": plan.warnings,
        "issues": plan.issues,
        "comment": plan.comment,
    }
    values.update(changes)
    return ReportPagePlan(**values)


def export_report_pdf(data: ReportData, output: str | Path) -> Path:
    from PySide6.QtCore import QMarginsF, QRectF, Qt
    from PySide6.QtGui import QColor, QFont, QFontMetricsF, QImage, QPageLayout, QPageSize, QPainter, QPdfWriter, QPen

    path = Path(output).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    writer = QPdfWriter(str(path))
    writer.setResolution(144)
    writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    writer.setPageMargins(QMarginsF(0, 0, 0, 0), QPageLayout.Unit.Millimeter)
    painter = QPainter(writer)
    if not painter.isActive():
        raise RuntimeError("PDF 출력 장치를 시작하지 못했습니다")
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    plans = plan_report_pages(data)
    for index, plan in enumerate(plans):
        if index:
            writer.newPage()
        canvas = QRectF(0, 0, writer.width(), writer.height())
        ctx = (Qt, QColor, QFont, QFontMetricsF, QPen, QRectF, QImage)
        _draw_page(painter, canvas, data, plan, index + 1, len(plans), index == len(plans) - 1, ctx)
    painter.end()
    if not path.is_file() or path.stat().st_size == 0:
        raise RuntimeError("PDF 보고서를 생성하지 못했습니다")
    return path


def _draw_page(p, canvas, data, plan, page_no, page_count, is_last, ctx):
    Qt, QColor, QFont, QFontMetricsF, QPen, QRectF, QImage = ctx
    scale = canvas.width() / 1191.0
    margin = 92 * scale
    footer_h = 72 * scale
    content = QRectF(margin, 0, canvas.width() - margin * 2, canvas.height())
    text = QColor(REPORT_COLORS["text"])
    secondary = QColor(REPORT_COLORS["secondary"])
    primary = QColor(report_primary_color(data.branding))

    p.fillRect(canvas, QColor(REPORT_COLORS["background"]))

    def font(size, weight=QFont.Weight.Normal):
        result = QFont("Malgun Gothic", size, weight)
        result.setStyleHint(QFont.StyleHint.SansSerif)
        return result

    def draw(rect, value, size=10, color=text, weight=QFont.Weight.Normal, flags=None):
        p.setPen(color); p.setFont(font(size, weight))
        p.drawText(rect, flags or (Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), value)

    y = 66 * scale
    if plan.kind == "summary":
        y = _draw_hero(p, data, content, y, scale, draw, primary, ctx)
        y += 26 * scale
        y = _draw_kpis(p, data, margin, y, content.width(), scale, draw, ctx)
        y += 24 * scale
        draw(QRectF(margin, y, content.width(), 34 * scale), "핵심 결과 요약", 15, text, QFont.Weight.Bold)
        y += 44 * scale
        y = _draw_insights(p, data, margin, y, content.width(), scale, draw, ctx)
        y += 28 * scale
        draw(QRectF(margin, y, content.width(), 34 * scale), "전체 보장 요약", 15, text, QFont.Weight.Bold)
        y += 44 * scale
        y = _draw_aggregate_cards(p, plan.aggregates, margin, y, content.width(), scale, draw, ctx, compact=True)
        if plan.contracts and y < canvas.height() - 310 * scale:
            y += 24 * scale
            draw(QRectF(margin, y, content.width(), 34 * scale), "가입된 치아보험 상품", 14, text, QFont.Weight.Bold)
            y += 42 * scale
            _draw_contract_cards(p, plan.contracts, margin, y, content.width(), scale, draw, ctx, compact=True)
        elif not data.contracts and y < canvas.height() - 230 * scale:
            y += 24 * scale
            draw(QRectF(margin, y, content.width(), 34 * scale), "가입된 치아보험 상품", 14, text, QFont.Weight.Bold)
            y += 42 * scale
            _draw_empty(p, QRectF(margin, y, content.width(), 84 * scale), "가입된 치아보험이 없습니다", "원본 문서에서 확인 가능한 치아보험 상품이 없습니다.", draw, ctx)
            y += 106 * scale
        if not data.riders and y < canvas.height() - 250 * scale:
            y += 20 * scale
            draw(QRectF(margin, y, content.width(), 34 * scale), "세부 치아담보", 14, text, QFont.Weight.Bold)
            y += 42 * scale
            _draw_empty(p, QRectF(margin, y, content.width(), 84 * scale), "세부 치아담보가 없습니다", "원본 문서에서 확인 가능한 세부 치아담보가 없습니다.", draw, ctx)
    elif plan.kind == "aggregates":
        y = _draw_section_header(p, content, y, "전체 보장 요약", "추가 확인된 보장 항목", draw, ctx, "#4F7CAC")
        _draw_aggregate_cards(p, plan.aggregates, margin, y, content.width(), scale, draw, ctx)
    elif plan.kind == "contracts":
        y = _draw_section_header(p, content, y, "가입된 치아보험 상품", "원본 자료에서 확인된 계약 정보", draw, ctx, "#4BC9A7")
        _draw_contract_cards(p, plan.contracts, margin, y, content.width(), scale, draw, ctx)
    elif plan.kind == "riders":
        y = _draw_section_header(p, content, y, "세부 치아담보", "지급조건과 지급단위가 다른 담보는 합산하지 않았습니다", draw, ctx, "#7C6FF0")
        _draw_riders(p, plan.riders, margin, y, content.width(), scale, draw, ctx)
    elif plan.kind == "issues":
        y = _draw_section_header(p, content, y, "확인 필요 항목", "상담 전 원본 확인이 필요한 항목", draw, ctx, "#F59E0B")
        _draw_issues(p, plan.issues, margin, y, content.width(), scale, draw, ctx)
    else:
        y = _draw_section_header(p, content, y, "상담 코멘트", "보고서에 표시할 상담 메모", draw, ctx, "#234A75")

    if plan.comment:
        comment_top = max(y + 20 * scale, 210 * scale)
        _draw_comment(p, plan.comment, margin, comment_top, content.width(), canvas.height() - comment_top - footer_h - 150 * scale, scale, draw, ctx)
    if is_last:
        _draw_branding_and_disclaimer(p, data, margin, canvas.height() - footer_h - 214 * scale, content.width(), scale, draw, ctx)
    _draw_footer(p, data, content, canvas, page_no, page_count, footer_h, scale, draw, ctx)


def _draw_hero(p, data, content, y, scale, draw, primary, ctx):
    Qt, QColor, QFont, _, _, QRectF, QImage = ctx
    rect = QRectF(content.left(), y, content.width(), 188 * scale)
    p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor(REPORT_COLORS["surface"])); p.drawRoundedRect(rect, 22 * scale, 22 * scale)
    p.setBrush(primary); p.drawRoundedRect(QRectF(rect.left(), rect.top(), rect.width(), 8 * scale), 4 * scale, 4 * scale)
    left = rect.left() + 30 * scale
    draw(QRectF(left, rect.top() + 24 * scale, rect.width() - 60 * scale, 24 * scale), "DENTAL COVERAGE ANALYSIS", 8.5, primary, QFont.Weight.Bold)
    draw(QRectF(left, rect.top() + 53 * scale, rect.width() - 250 * scale, 54 * scale), "치아보험 보장분석표", 25, QColor(REPORT_COLORS["text"]), QFont.Weight.Bold)
    draw(QRectF(left, rect.top() + 111 * scale, rect.width() - 60 * scale, 28 * scale), "고객님의 치아 관련 보장 현황과 보완 필요 항목을 정리한 보고서", 9.5, QColor(REPORT_COLORS["secondary"]))
    meta = f"고객명  {data.customer_name}     ·     분석일  {data.analysis_date.isoformat()}     ·     치아보험 상품  {len(data.contracts)}개"
    draw(QRectF(left, rect.bottom() - 42 * scale, rect.width() - 60 * scale, 26 * scale), meta, 9, QColor(REPORT_COLORS["secondary"]))
    if data.branding.company_name:
        draw(QRectF(rect.right() - 330 * scale, rect.top() + 25 * scale, 290 * scale, 28 * scale), data.branding.company_name, 10, primary, QFont.Weight.Bold, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    if data.branding.logo_path and Path(data.branding.logo_path).is_file():
        logo = QImage(data.branding.logo_path)
        if not logo.isNull():
            box = QRectF(rect.right() - 170 * scale, rect.top() + 66 * scale, 125 * scale, 60 * scale)
            scaled = logo.scaled(int(box.width()), int(box.height()), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            target = QRectF(box.right() - scaled.width(), box.top() + (box.height() - scaled.height()) / 2, scaled.width(), scaled.height())
            p.drawImage(target, scaled)
    return rect.bottom()


def _kpi_items(data):
    missing = sum(1 for item in data.aggregates if item.status == "미가입")
    shortage = sum(1 for item in data.aggregates if item.status == "부족")
    review = sum(1 for item in data.aggregates if item.needs_review or item.status in {"확인 필요", "정보 확인 필요"} or item.ratio is None)
    review += len(data.validation_issues) + len(data.aggregate_warnings)
    return (
        ("상품 수", f"{len(data.contracts)}개"),
        ("세부 담보", f"{len(data.riders)}개"),
        ("부족 항목", f"{shortage}개"),
        ("미가입 항목", f"{missing}개"),
        ("확인 필요", f"{review}개"),
    )


def _draw_kpis(p, data, x, y, width, scale, draw, ctx):
    Qt, QColor, QFont, _, QPen, QRectF, _ = ctx
    gap = 12 * scale
    card_w = (width - gap * 4) / 5
    for index, (label, value) in enumerate(_kpi_items(data)):
        rect = QRectF(x + index * (card_w + gap), y, card_w, 100 * scale)
        p.setPen(QPen(QColor(REPORT_COLORS["border"]), 1)); p.setBrush(QColor("#FFFFFF")); p.drawRoundedRect(rect, 14 * scale, 14 * scale)
        draw(QRectF(rect.left() + 16 * scale, rect.top() + 14 * scale, rect.width() - 32 * scale, 22 * scale), label, 8.5, QColor(REPORT_COLORS["secondary"]))
        draw(QRectF(rect.left() + 16 * scale, rect.top() + 42 * scale, rect.width() - 32 * scale, 38 * scale), value, 18, QColor(REPORT_COLORS["primary"]), QFont.Weight.Bold)
    return y + 100 * scale


def _priority_items(data):
    items = [item for item in data.aggregates if item.status in {"미가입", "부족"} or item.needs_review]
    items.sort(key=lambda item: (0 if item.status == "미가입" else 1 if item.status == "부족" else 2, -(item.shortage_amount or 0), item.name))
    return items[:3]


def _draw_insights(p, data, x, y, width, scale, draw, ctx):
    Qt, QColor, QFont, _, QPen, QRectF, _ = ctx
    rect = QRectF(x, y, width, 122 * scale)
    p.setPen(QPen(QColor(REPORT_COLORS["border"]), 1)); p.setBrush(QColor("#FFFFFF")); p.drawRoundedRect(rect, 16 * scale, 16 * scale)
    columns = [
        ("보완 추천", _priority_items(data), "#F59E0B"),
        ("충분한 항목", [item for item in data.aggregates if item.status == "충분"][:3], "#2E8B57"),
        ("미가입 항목", [item for item in data.aggregates if item.status == "미가입"][:3], "#E15759"),
    ]
    col_w = rect.width() / 3
    for index, (title, items, color) in enumerate(columns):
        left = rect.left() + index * col_w
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor(color)); p.drawRoundedRect(QRectF(left + 18 * scale, rect.top() + 18 * scale, 5 * scale, 28 * scale), 2 * scale, 2 * scale)
        draw(QRectF(left + 32 * scale, rect.top() + 16 * scale, col_w - 46 * scale, 30 * scale), title, 10.5, QColor(REPORT_COLORS["text"]), QFont.Weight.Bold)
        lines = [item.name for item in items] or ["해당 항목 없음"]
        body = "\n".join(f"- {line}" for line in lines[:3])
        draw(QRectF(left + 32 * scale, rect.top() + 48 * scale, col_w - 46 * scale, 60 * scale), body, 8.5, QColor(REPORT_COLORS["secondary"]), flags=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap)
    return rect.bottom()


def _draw_section_header(p, content, y, title, subtitle, draw, ctx, color):
    Qt, QColor, QFont, _, _, QRectF, _ = ctx
    p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor(color)); p.drawRoundedRect(QRectF(content.left(), y + 8, 7, 38), 3, 3)
    draw(QRectF(content.left() + 18, y, content.width() - 18, 42), title, 21, QColor(REPORT_COLORS["text"]), QFont.Weight.Bold)
    y += 50
    draw(QRectF(content.left() + 18, y, content.width() - 18, 30), subtitle, 9.5, QColor(REPORT_COLORS["secondary"]))
    return y + 50


def _draw_aggregate_cards(p, items, x, y, width, scale, draw, ctx, compact=False):
    Qt, QColor, QFont, _, _, QRectF, _ = ctx
    if not items:
        rect = QRectF(x, y, width, 132 * scale)
        _draw_empty(p, rect, "전체 치아보장 정보를 확인하지 못했습니다", "원본 문서에서 표시 가능한 치아 보장 요약 항목이 없습니다.", draw, ctx)
        return rect.bottom()
    gap = 18 * scale
    card_w = (width - gap) / 2
    card_h = (238 if compact else 275) * scale
    for index, item in enumerate(items):
        col, row = index % 2, index // 2
        rect = QRectF(x + col * (card_w + gap), y + row * (card_h + gap), card_w, card_h)
        _draw_aggregate_card(p, rect, item, scale, draw, ctx)
    rows = (len(items) + 1) // 2
    return y + rows * card_h + max(rows - 1, 0) * gap


def _draw_badge(p, rect, text, bg, fg, draw, ctx, size=8.2):
    Qt, QColor, QFont, _, _, _, _ = ctx
    p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor(bg)); p.drawRoundedRect(rect, rect.height() / 2, rect.height() / 2)
    draw(rect, text, size, QColor(fg), QFont.Weight.Bold, Qt.AlignmentFlag.AlignCenter)


def _draw_aggregate_card(p, rect, item, scale, draw, ctx):
    Qt, QColor, QFont, _, QPen, QRectF, _ = ctx
    color = CATEGORY_COLORS.get(item.category, DEFAULT_COLOR)
    p.setPen(QPen(QColor(REPORT_COLORS["border"]), 1)); p.setBrush(QColor("#FFFFFF")); p.drawRoundedRect(rect, 16 * scale, 16 * scale)
    _draw_badge(p, QRectF(rect.left() + 18 * scale, rect.top() + 16 * scale, 94 * scale, 26 * scale), item.category, color, "#FFFFFF", draw, ctx)
    status = item.status or "정보 확인 필요"
    bg, fg = status_style(status, needs_review=item.needs_review)
    _draw_badge(p, QRectF(rect.right() - 130 * scale, rect.top() + 16 * scale, 110 * scale, 26 * scale), status, bg, fg, draw, ctx, size=7.8)
    draw(QRectF(rect.left() + 18 * scale, rect.top() + 52 * scale, rect.width() - 36 * scale, 34 * scale), item.name, 11.8, QColor(REPORT_COLORS["text"]), QFont.Weight.Bold, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextWordWrap)
    metrics = (
        ("가입금액", format_money(item.enrolled_amount)),
        ("권장금액", format_money(item.recommended_amount)),
        ("부족금액", format_money(item.shortage_amount)),
        ("보장률", "정보 확인 필요" if item.ratio is None else f"{item.ratio:.0f}%"),
    )
    top = rect.top() + 100 * scale
    box_w = (rect.width() - 50 * scale) / 2
    for index, (label, value) in enumerate(metrics):
        row, col = index // 2, index % 2
        bx = rect.left() + 18 * scale + col * (box_w + 14 * scale)
        by = top + row * 48 * scale
        draw(QRectF(bx, by, box_w, 18 * scale), label, 8, QColor(REPORT_COLORS["secondary"]))
        draw(QRectF(bx, by + 18 * scale, box_w, 24 * scale), value, 10.8, QColor(REPORT_COLORS["text"]), QFont.Weight.Bold)
    bar = QRectF(rect.left() + 18 * scale, rect.bottom() - 40 * scale, rect.width() - 36 * scale, 7 * scale)
    p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor("#EEF2F6")); p.drawRoundedRect(bar, 4 * scale, 4 * scale)
    if item.ratio is not None:
        filled = QRectF(bar.left(), bar.top(), bar.width() * min(max(item.ratio, 0), 100) / 100, bar.height())
        p.setBrush(QColor(color)); p.drawRoundedRect(filled, 4 * scale, 4 * scale)
    source = f"원본 {item.source_page}페이지" if item.source_page else "원본 페이지 정보 없음"
    draw(QRectF(rect.left() + 18 * scale, rect.bottom() - 26 * scale, rect.width() - 36 * scale, 18 * scale), source, 7.8, QColor(REPORT_COLORS["secondary"]))


def _draw_contract_cards(p, items, x, y, width, scale, draw, ctx, compact=False):
    Qt, QColor, QFont, _, QPen, QRectF, _ = ctx
    card_h = (104 if compact else 138) * scale
    for item in items:
        rect = QRectF(x, y, width, card_h)
        p.setPen(QPen(QColor(REPORT_COLORS["border"]), 1)); p.setBrush(QColor("#FFFFFF")); p.drawRoundedRect(rect, 14 * scale, 14 * scale)
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor("#4F7CAC")); p.drawRoundedRect(QRectF(rect.left(), rect.top(), 6 * scale, rect.height()), 3 * scale, 3 * scale)
        draw(QRectF(rect.left() + 24 * scale, rect.top() + 16 * scale, rect.width() - 48 * scale, 24 * scale), item.insurer or "보험사 정보 없음", 9, QColor(REPORT_COLORS["primary"]), QFont.Weight.Bold)
        draw(QRectF(rect.left() + 24 * scale, rect.top() + 42 * scale, rect.width() - 48 * scale, 36 * scale), item.product_name or "상품명 정보 없음", 12.5, QColor(REPORT_COLORS["text"]), QFont.Weight.Bold, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextWordWrap)
        detail = f"보험기간  {item.coverage_period or '정보 없음'}     월 보험료  {format_money(item.monthly_premium)}"
        draw(QRectF(rect.left() + 24 * scale, rect.bottom() - 28 * scale, rect.width() - 48 * scale, 22 * scale), detail, 8.5, QColor(REPORT_COLORS["secondary"]))
        y = rect.bottom() + 14 * scale
    return y


def _draw_riders(p, items, x, y, width, scale, draw, ctx):
    Qt, QColor, QFont, _, QPen, QRectF, _ = ctx
    if not items:
        _draw_empty(p, QRectF(x, y, width, 132 * scale), "세부 치아담보가 없습니다", "원본 문서에서 확인 가능한 세부 치아담보가 없습니다.", draw, ctx)
        return
    current = None
    for item in items:
        if item.category != current:
            current = item.category
            color = QColor(CATEGORY_COLORS.get(current, DEFAULT_COLOR))
            header = QRectF(x, y, width, 42 * scale)
            p.setPen(QPen(QColor(REPORT_COLORS["border"]), 1)); p.setBrush(QColor("#FFFFFF")); p.drawRoundedRect(header, 10 * scale, 10 * scale)
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(color); p.drawRoundedRect(QRectF(header.left(), header.top(), 7 * scale, header.height()), 3 * scale, 3 * scale)
            draw(header.adjusted(20 * scale, 0, -20 * scale, 0), current, 11, QColor(REPORT_COLORS["text"]), QFont.Weight.Bold)
            y = header.bottom() + 9 * scale
        row = QRectF(x, y, width, 70 * scale)
        p.setPen(QPen(QColor(REPORT_COLORS["border"]), 1)); p.setBrush(QColor("#FFFFFF")); p.drawRoundedRect(row, 10 * scale, 10 * scale)
        draw(QRectF(row.left() + 18 * scale, row.top() + 10 * scale, row.width() * .55, 24 * scale), item.name, 10.2, QColor(REPORT_COLORS["text"]), QFont.Weight.Bold)
        meta = f"{item.insurer or '보험사 정보 없음'} · {item.product_name or '상품명 정보 없음'}"
        draw(QRectF(row.left() + 18 * scale, row.top() + 36 * scale, row.width() * .55, 22 * scale), meta, 7.8, QColor(REPORT_COLORS["secondary"]))
        draw(QRectF(row.right() - 360 * scale, row.top() + 12 * scale, 150 * scale, 42 * scale), item.cause_type, 8.5, QColor(REPORT_COLORS["secondary"]), flags=Qt.AlignmentFlag.AlignCenter)
        draw(QRectF(row.right() - 235 * scale, row.top() + 12 * scale, 90 * scale, 42 * scale), item.payment_unit, 8.5, QColor(REPORT_COLORS["secondary"]), flags=Qt.AlignmentFlag.AlignCenter)
        draw(QRectF(row.right() - 138 * scale, row.top() + 12 * scale, 116 * scale, 42 * scale), format_money(item.amount), 10.5, QColor(REPORT_COLORS["text"]), QFont.Weight.Bold, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        y = row.bottom() + 8 * scale


def _draw_issues(p, issues, x, y, width, scale, draw, ctx):
    Qt, QColor, QFont, _, QPen, QRectF, _ = ctx
    if not issues:
        _draw_empty(p, QRectF(x, y, width, 132 * scale), "확인 필요 항목이 없습니다", "자동 분석 결과에서 별도 확인이 필요한 항목이 표시되지 않았습니다.", draw, ctx)
        return
    for issue in issues:
        bg, fg, label = SEVERITY_STYLES.get(issue.severity.value, SEVERITY_STYLES["INFO"])
        rect = QRectF(x, y, width, 82 * scale)
        p.setPen(QPen(QColor(REPORT_COLORS["border"]), 1)); p.setBrush(QColor("#FFFFFF")); p.drawRoundedRect(rect, 12 * scale, 12 * scale)
        _draw_badge(p, QRectF(rect.left() + 18 * scale, rect.top() + 18 * scale, 72 * scale, 26 * scale), label, bg, fg, draw, ctx)
        pages = ", ".join(map(str, issue.page_numbers))
        message = issue.message + (f" · 원본 {pages}페이지" if pages else "")
        draw(QRectF(rect.left() + 106 * scale, rect.top() + 12 * scale, rect.width() - 126 * scale, rect.height() - 24 * scale), message, 9.5, QColor(REPORT_COLORS["text"]), flags=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextWordWrap)
        y = rect.bottom() + 10 * scale


def _draw_comment(p, comment, x, y, width, available_h, scale, draw, ctx):
    Qt, QColor, QFont, _, QPen, QRectF, _ = ctx
    rect = QRectF(x, y, width, max(118 * scale, min(available_h, 245 * scale)))
    p.setPen(QPen(QColor(REPORT_COLORS["border"]), 1)); p.setBrush(QColor("#FFFFFF")); p.drawRoundedRect(rect, 14 * scale, 14 * scale)
    p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor(REPORT_COLORS["primary"])); p.drawRoundedRect(QRectF(rect.left(), rect.top(), 7 * scale, rect.height()), 3 * scale, 3 * scale)
    draw(QRectF(rect.left() + 24 * scale, rect.top() + 14 * scale, rect.width() - 48 * scale, 26 * scale), "상담 코멘트", 12, QColor(REPORT_COLORS["primary"]), QFont.Weight.Bold)
    draw(QRectF(rect.left() + 24 * scale, rect.top() + 46 * scale, rect.width() - 48 * scale, rect.height() - 58 * scale), comment, 9.5, QColor(REPORT_COLORS["text"]), flags=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap)


def _draw_empty(p, rect, title, description, draw, ctx):
    Qt, QColor, QFont, _, QPen, QRectF, _ = ctx
    p.setPen(QPen(QColor(REPORT_COLORS["border"]), 1)); p.setBrush(QColor("#FFFFFF")); p.drawRoundedRect(rect, 14, 14)
    draw(QRectF(rect.left() + 22, rect.top() + 16, rect.width() - 44, 28), title, 11.5, QColor(REPORT_COLORS["text"]), QFont.Weight.Bold)
    draw(QRectF(rect.left() + 22, rect.top() + 46, rect.width() - 44, rect.height() - 58), description, 9, QColor(REPORT_COLORS["secondary"]), flags=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap)


def _draw_branding_and_disclaimer(p, data, x, y, width, scale, draw, ctx):
    Qt, QColor, QFont, _, QPen, QRectF, _ = ctx
    brand = data.branding
    contacts = " · ".join(filter(None, (
        brand.company_name,
        f"담당자 {brand.consultant_name}" if brand.consultant_name else "",
        brand.phone,
        brand.email,
    )))
    brand_text = "\n".join(value for value in (contacts, brand.footer_text.strip()) if value)
    if brand_text:
        rect = QRectF(x, y, width, 72 * scale)
        p.setPen(QPen(QColor(REPORT_COLORS["border"]), 1)); p.setBrush(QColor("#FFFFFF")); p.drawRoundedRect(rect, 12 * scale, 12 * scale)
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor(report_primary_color(brand))); p.drawRoundedRect(QRectF(rect.left(), rect.top(), 6 * scale, rect.height()), 3 * scale, 3 * scale)
        draw(rect.adjusted(18 * scale, 8 * scale, -18 * scale, -8 * scale), brand_text, 8.4, QColor(REPORT_COLORS["secondary"]), QFont.Weight.Bold, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextWordWrap)
        y = rect.bottom() + 14 * scale
    disclaimer = DISCLAIMER + " 서로 다른 지급단위의 세부 담보는 단순 합산하지 않았습니다."
    box = QRectF(x, y, width, 96 * scale)
    p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor("#EEF2F6")); p.drawRoundedRect(box, 12 * scale, 12 * scale)
    draw(box.adjusted(18 * scale, 10 * scale, -18 * scale, -10 * scale), disclaimer, 8, QColor(REPORT_COLORS["secondary"]), flags=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextWordWrap)


def _draw_footer(p, data, content, canvas, page_no, page_count, footer_h, scale, draw, ctx):
    Qt, QColor, QFont, _, QPen, QRectF, _ = ctx
    y = canvas.height() - footer_h + 14 * scale
    p.setPen(QPen(QColor(REPORT_COLORS["border"]), 1))
    p.drawLine(content.left(), y, content.right(), y)
    left = data.branding.company_name or "치아보험 보장분석표"
    note = "자동 정리 참고자료"
    draw(QRectF(content.left(), y + 10 * scale, content.width() * .62, 24 * scale), f"{left} · {note}", 7.8, QColor(REPORT_COLORS["secondary"]))
    draw(QRectF(content.left(), y + 30 * scale, content.width() * .62, 22 * scale), f"생성일 {data.analysis_date.isoformat()}", 7.5, QColor(REPORT_COLORS["muted"]))
    draw(QRectF(content.right() - 170 * scale, y + 11 * scale, 170 * scale, 30 * scale), f"{page_no} / {page_count}", 8.2, QColor(REPORT_COLORS["secondary"]), QFont.Weight.Bold, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
