from __future__ import annotations

from typing import Any

from dental_coverage_analyzer.models import PDFBlock, PDFPageData, PDFWord


def extract_page_layout(page: Any, page_number: int | None = None) -> PDFPageData:
    """페이지의 텍스트와 2차원 word/block layout을 손실 없이 옮긴다."""
    words = [
        PDFWord(
            text=str(item[4]),
            x0=float(item[0]), y0=float(item[1]), x1=float(item[2]), y1=float(item[3]),
            block_no=int(item[5]), line_no=int(item[6]), word_no=int(item[7]),
        )
        for item in page.get_text("words", sort=False)
        if len(item) >= 8 and str(item[4]).strip()
    ]
    blocks = [
        PDFBlock(
            text=str(item[4]),
            x0=float(item[0]), y0=float(item[1]), x1=float(item[2]), y1=float(item[3]),
            block_no=int(item[5]) if len(item) > 5 else index,
            block_type=int(item[6]) if len(item) > 6 else 0,
        )
        for index, item in enumerate(page.get_text("blocks", sort=False))
        if len(item) >= 5
    ]
    rect = page.rect
    return PDFPageData(
        page_number=page_number if page_number is not None else page.number + 1,
        width=float(rect.width),
        height=float(rect.height),
        text=page.get_text("text", sort=False),
        words=words,
        blocks=blocks,
    )
