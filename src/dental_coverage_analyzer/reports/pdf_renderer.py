from __future__ import annotations

from dataclasses import dataclass, field, replace
import textwrap
from pathlib import Path

from .generator import DISCLAIMER, format_money
from .theme import CATEGORY_COLORS, DEFAULT_COLOR
from .view_models import ReportAggregate, ReportContract, ReportData, ReportRider


@dataclass(frozen=True, slots=True)
class ReportPagePlan:
    kind: str
    aggregates: tuple[ReportAggregate, ...] = field(default_factory=tuple)
    contracts: tuple[ReportContract, ...] = field(default_factory=tuple)
    riders: tuple[ReportRider, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)
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


def plan_report_pages(data: ReportData) -> tuple[ReportPagePlan, ...]:
    """콘텐츠가 존재하는 페이지만 만들며 소량 계약은 첫 페이지 여백에 배치한다."""
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
    if data.riders:
        for start in range(0, len(data.riders), 7):
            pages.append(ReportPagePlan("riders", riders=data.riders[start:start + 7]))
    if data.comment.strip():
        can_attach = (
            pages[-1].kind == "summary" and len(data.aggregates) <= 2
            and len(data.aggregate_warnings) <= 1 and len(data.contracts) <= 2
            and len(_comment_lines(data.comment)) <= 10
        )
        if can_attach:
            pages[-1] = replace(pages[-1], comment=data.comment)
        else:
            pages.extend(ReportPagePlan("comment", comment=chunk) for chunk in _comment_chunks(data.comment))
    return tuple(pages)


def export_report_pdf(data: ReportData, output: str | Path) -> Path:
    from PySide6.QtCore import QMarginsF, QRectF, Qt
    from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPageLayout, QPageSize, QPainter, QPdfWriter, QPen

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
        _draw_page(painter, canvas, data, plan, index + 1, len(plans), index == len(plans) - 1, Qt, QColor, QFont, QFontMetricsF, QPen, QRectF)
    painter.end()
    if not path.is_file() or path.stat().st_size == 0:
        raise RuntimeError("PDF 보고서를 생성하지 못했습니다")
    return path


def _draw_page(p, canvas, data, plan, page_no, page_count, is_last, Qt, QColor, QFont, QFontMetricsF, QPen, QRectF):
    bg = QColor("#F7F8FC"); text = QColor("#252A3D"); secondary = QColor("#858CA0")
    p.fillRect(canvas, bg)
    scale = canvas.width() / 1191.0
    margin = 106 * scale
    content = QRectF(margin, 0, canvas.width() - margin * 2, canvas.height())

    def font(size, weight=QFont.Weight.Normal):
        result = QFont("Malgun Gothic", size, weight)
        result.setStyleHint(QFont.StyleHint.SansSerif)
        return result

    def draw_label(rect, value, size=10, color=text, weight=QFont.Weight.Normal, flags=None):
        p.setPen(color); p.setFont(font(size, weight))
        p.drawText(rect, flags or (Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), value)

    y = 72 * scale
    if plan.kind == "summary":
        header = QRectF(margin, y, content.width(), 190 * scale)
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor("#EFEEFF")); p.drawRoundedRect(header, 28 * scale, 28 * scale)
        draw_label(QRectF(header.left() + 34 * scale, header.top() + 22 * scale, header.width() - 68 * scale, 28 * scale), "DENTAL COVERAGE ANALYSIS", 9, QColor("#625EF5"), QFont.Weight.Bold)
        draw_label(QRectF(header.left() + 34 * scale, header.top() + 53 * scale, header.width() - 68 * scale, 62 * scale), "치아보험 보장분석표", 25, text, QFont.Weight.Bold)
        meta = f"고객명  {data.customer_name}     ·     분석일  {data.analysis_date.isoformat()}"
        draw_label(QRectF(header.left() + 34 * scale, header.bottom() - 54 * scale, header.width() - 68 * scale, 30 * scale), meta, 10, secondary)
        y = header.bottom() + 46 * scale
        draw_label(QRectF(margin, y, content.width(), 38 * scale), "전체 치아보장 요약", 17, text, QFont.Weight.Bold)
        y += 58 * scale
        y = _draw_aggregate_cards(p, plan.aggregates, margin, y, content.width(), scale, draw_label, Qt, QColor, QFont, QRectF)
        for warning in plan.warnings[:2]:
            warning_rect = QRectF(margin, y + 12 * scale, content.width(), 70 * scale)
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor("#FFF7E8")); p.drawRoundedRect(warning_rect, 14 * scale, 14 * scale)
            draw_label(warning_rect.adjusted(20 * scale, 8 * scale, -20 * scale, -8 * scale), "⚠ " + warning, 8.5, QColor("#9A681E"), flags=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextWordWrap)
            y = warning_rect.bottom()
        if plan.contracts:
            y += 34 * scale
            draw_label(QRectF(margin, y, content.width(), 34 * scale), "가입된 치아보험", 15, text, QFont.Weight.Bold)
            y += 44 * scale
            y = _draw_contract_cards(p, plan.contracts, margin, y, content.width(), scale, draw_label, Qt, QColor, QFont, QRectF, compact=True)
        elif not data.contracts:
            y += 34 * scale
            draw_label(QRectF(margin, y, content.width(), 34 * scale), "가입된 치아보험", 15, text, QFont.Weight.Bold)
            y += 44 * scale
            empty = QRectF(margin, y, content.width(), 72 * scale)
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor("#FFFFFF")); p.drawRoundedRect(empty, 16 * scale, 16 * scale)
            draw_label(empty.adjusted(22 * scale, 0, -22 * scale, 0), "없음", 14, text, QFont.Weight.Bold)
    elif plan.kind == "aggregates":
        y = _draw_section_header(p, content, y, "전체 치아보장 요약", "추가 확인 항목", draw_label, QColor, Qt, QRectF, scale)
        _draw_aggregate_cards(p, plan.aggregates, margin, y, content.width(), scale, draw_label, Qt, QColor, QFont, QRectF)
    elif plan.kind == "contracts":
        y = _draw_section_header(p, content, y, "가입된 치아보험", "원본 자료에서 확인된 계약정보", draw_label, QColor, Qt, QRectF, scale)
        _draw_contract_cards(p, plan.contracts, margin, y, content.width(), scale, draw_label, Qt, QColor, QFont, QRectF)
    elif plan.kind == "riders":
        y = _draw_section_header(p, content, y, "세부 치아보장", "지급조건과 지급단위가 다른 담보는 합산하지 않았습니다", draw_label, QColor, Qt, QRectF, scale)
        _draw_riders(p, plan.riders, margin, y, content.width(), scale, draw_label, Qt, QColor, QFont, QRectF)
    else:
        y = 90 * scale

    if plan.comment:
        disclaimer_top = canvas.height() - 190 * scale if is_last else canvas.height() - 70 * scale
        p.setFont(font(10))
        flags = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap
        measured = QFontMetricsF(p.font()).boundingRect(
            QRectF(0, 0, content.width() - 48 * scale, canvas.height()), flags, plan.comment,
        )
        comment_height = max(112 * scale, measured.height() + 72 * scale)
        comment_top = max(y + 24 * scale, disclaimer_top - comment_height - 18 * scale)
        comment_rect = QRectF(margin, comment_top, content.width(), comment_height)
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor("#F1F0FF")); p.drawRoundedRect(comment_rect, 16 * scale, 16 * scale)
        draw_label(QRectF(comment_rect.left() + 24 * scale, comment_rect.top() + 14 * scale, comment_rect.width() - 48 * scale, 30 * scale), "상담 코멘트", 12, QColor("#625EF5"), QFont.Weight.Bold)
        draw_label(QRectF(comment_rect.left() + 24 * scale, comment_rect.top() + 48 * scale, comment_rect.width() - 48 * scale, comment_rect.height() - 62 * scale), plan.comment, 10, text, flags=flags)

    if is_last:
        box = QRectF(margin, canvas.height() - 190 * scale, content.width(), 105 * scale)
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor("#EEF0F5")); p.drawRoundedRect(box, 12 * scale, 12 * scale)
        disclaimer = DISCLAIMER + " 서로 다른 지급단위의 세부 담보는 단순 합산하지 않았습니다."
        draw_label(box.adjusted(18 * scale, 10 * scale, -18 * scale, -10 * scale), disclaimer, 8.5, secondary, flags=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextWordWrap)
    draw_label(QRectF(margin, canvas.height() - 58 * scale, content.width(), 24 * scale), f"{page_no} / {page_count}", 8.5, secondary, flags=Qt.AlignmentFlag.AlignCenter)


def _draw_section_header(p, content, y, title, subtitle, draw, QColor, Qt, QRectF, scale):
    draw(QRectF(content.left(), y, content.width(), 48 * scale), title, 24, QColor("#252A3D"), 700)
    y += 58 * scale
    draw(QRectF(content.left(), y, content.width(), 30 * scale), subtitle, 10, QColor("#858CA0"))
    return y + 54 * scale


def _draw_aggregate_cards(p, items, x, y, width, scale, draw, Qt, QColor, QFont, QRectF):
    if not items:
        rect = QRectF(x, y, width, 150 * scale); p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor("#FFFFFF")); p.drawRoundedRect(rect, 20 * scale, 20 * scale)
        draw(rect.adjusted(28 * scale, 0, -28 * scale, 0), "전체 치아보장 정보를 확인하지 못했습니다.", 12, QColor("#858CA0"))
        return rect.bottom()
    gap = 22 * scale; card_width = (width - gap) / 2; card_height = 350 * scale
    for index, item in enumerate(items):
        col, row = index % 2, index // 2
        rect = QRectF(x + col * (card_width + gap), y + row * (card_height + gap), card_width, card_height)
        _draw_aggregate_card(p, rect, item, scale, draw, Qt, QColor, QFont, QRectF)
    rows = (len(items) + 1) // 2
    return y + rows * card_height + max(rows - 1, 0) * gap


def _draw_aggregate_card(p, rect, item, scale, draw, Qt, QColor, QFont, QRectF):
    color = QColor(CATEGORY_COLORS.get(item.category, DEFAULT_COLOR))
    p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor("#FFFFFF")); p.drawRoundedRect(rect, 22 * scale, 22 * scale)
    badge = QRectF(rect.left() + 24 * scale, rect.top() + 22 * scale, 105 * scale, 30 * scale)
    p.setBrush(color); p.drawRoundedRect(badge, 15 * scale, 15 * scale)
    draw(badge, item.category, 8.5, QColor("#FFFFFF"), QFont.Weight.Bold, Qt.AlignmentFlag.AlignCenter)
    draw(QRectF(rect.left() + 24 * scale, rect.top() + 62 * scale, rect.width() - 48 * scale, 42 * scale), item.name, 13, QColor("#252A3D"), QFont.Weight.Bold)
    draw(QRectF(rect.left() + 24 * scale, rect.top() + 112 * scale, rect.width() - 48 * scale, 48 * scale), format_money(item.enrolled_amount), 18, QColor("#252A3D"), QFont.Weight.Bold)
    draw(QRectF(rect.left() + 24 * scale, rect.top() + 155 * scale, rect.width() - 48 * scale, 24 * scale), "현재 가입금액", 9, QColor("#858CA0"))
    draw(QRectF(rect.left() + 24 * scale, rect.top() + 194 * scale, rect.width() - 48 * scale, 25 * scale), f"권장  {format_money(item.recommended_amount)}", 10, QColor("#596075"), QFont.Weight.Bold)
    draw(QRectF(rect.left() + 24 * scale, rect.top() + 220 * scale, rect.width() - 48 * scale, 25 * scale), f"부족  {format_money(item.shortage_amount)}", 9.5, QColor("#858CA0"))
    ratio_text = f"{item.ratio:.0f}%" if item.ratio is not None else "확인 필요"
    draw(QRectF(rect.left() + 24 * scale, rect.top() + 255 * scale, 110 * scale, 34 * scale), ratio_text, 15, color, QFont.Weight.Bold)
    draw(QRectF(rect.left() + 130 * scale, rect.top() + 259 * scale, rect.width() - 154 * scale, 25 * scale), "현재 보장률", 8.5, QColor("#858CA0"))
    bar = QRectF(rect.left() + 24 * scale, rect.top() + 296 * scale, rect.width() - 48 * scale, 6 * scale)
    p.setBrush(QColor("#E8EAF2")); p.drawRoundedRect(bar, 3 * scale, 3 * scale)
    if item.ratio is not None:
        filled = QRectF(bar.left(), bar.top(), bar.width() * min(max(item.ratio, 0), 100) / 100, bar.height())
        p.setBrush(color); p.drawRoundedRect(filled, 3 * scale, 3 * scale)
    status = item.status or "정보 확인 필요"
    draw(QRectF(rect.left() + 24 * scale, rect.bottom() - 39 * scale, rect.width() - 48 * scale, 24 * scale), status, 9, QColor("#EF6A75") if item.needs_review or status in {"부족", "미가입"} else QColor("#3DBB8A"), QFont.Weight.Bold)


def _draw_contract_cards(p, items, x, y, width, scale, draw, Qt, QColor, QFont, QRectF, compact=False):
    height = (125 if compact else 175) * scale
    for item in items:
        rect = QRectF(x, y, width, height); p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor("#FFFFFF")); p.drawRoundedRect(rect, 18 * scale, 18 * scale)
        badge = QRectF(rect.left() + 24 * scale, rect.top() + 20 * scale, 180 * scale, 28 * scale)
        p.setBrush(QColor("#EFEEFF")); p.drawRoundedRect(badge, 14 * scale, 14 * scale)
        draw(badge, item.insurer or "보험사 정보 없음", 8.5, QColor("#625EF5"), QFont.Weight.Bold, Qt.AlignmentFlag.AlignCenter)
        draw(QRectF(rect.left() + 24 * scale, rect.top() + 53 * scale, rect.width() - 48 * scale, 38 * scale), item.product_name or "상품명 정보 없음", 14, QColor("#252A3D"), QFont.Weight.Bold)
        detail = f"보험기간  {item.coverage_period or '정보 없음'}     월 보험료  {format_money(item.monthly_premium)}"
        draw(QRectF(rect.left() + 24 * scale, rect.bottom() - 42 * scale, rect.width() - 48 * scale, 28 * scale), detail, 9.5, QColor("#858CA0"))
        y = rect.bottom() + 18 * scale
    return y


def _draw_riders(p, items, x, y, width, scale, draw, Qt, QColor, QFont, QRectF):
    current_category = None
    for item in items:
        if item.category != current_category:
            current_category = item.category
            color = QColor(CATEGORY_COLORS.get(current_category, DEFAULT_COLOR))
            header = QRectF(x, y, width, 42 * scale); p.setPen(Qt.PenStyle.NoPen); p.setBrush(color); p.drawRoundedRect(header, 12 * scale, 12 * scale)
            draw(header.adjusted(18 * scale, 0, -18 * scale, 0), current_category, 11, QColor("#FFFFFF"), QFont.Weight.Bold)
            y = header.bottom() + 12 * scale
        row = QRectF(x, y, width, 90 * scale); p.setBrush(QColor("#FFFFFF")); p.drawRoundedRect(row, 14 * scale, 14 * scale)
        draw(QRectF(row.left() + 20 * scale, row.top() + 12 * scale, row.width() * .66, 30 * scale), item.name, 11.5, QColor("#252A3D"), QFont.Weight.Bold)
        meta = " · ".join(value for value in (item.category, item.cause_type, item.payment_unit) if value and value != "확인 필요") or "정보 확인 필요"
        draw(QRectF(row.left() + 20 * scale, row.top() + 47 * scale, row.width() * .66, 24 * scale), meta, 8.5, QColor("#858CA0"))
        draw(QRectF(row.right() - 250 * scale, row.top(), 225 * scale, row.height()), format_money(item.amount), 14, QColor("#252A3D"), QFont.Weight.Bold, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        y = row.bottom() + 10 * scale
