from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class RenderedPage:
    png_bytes: bytes
    width: int
    height: int
    dpi: int


def render_page_png(page: Any, dpi: int = 250, max_pixels: int = 25_000_000) -> RenderedPage:
    """원본 페이지를 변경하지 않고, 메모리 상 PNG 하나만 렌더링한다."""
    if not 72 <= dpi <= 600:
        raise ValueError("OCR DPI는 72~600 범위여야 합니다")
    scale = dpi / 72
    estimated = int(page.rect.width * scale) * int(page.rect.height * scale)
    if estimated > max_pixels:
        scale *= (max_pixels / estimated) ** 0.5
        dpi = max(72, int(scale * 72))
    pixmap = page.get_pixmap(dpi=dpi, alpha=False)
    return RenderedPage(pixmap.tobytes("png"), pixmap.width, pixmap.height, dpi)
