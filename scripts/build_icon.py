from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).parents[1]
SOURCE = ROOT / "assets" / "app_icon.svg"
OUTPUT = ROOT / "build" / "generated" / "app_icon.ico"
SIZES = (16, 24, 32, 48, 64, 128, 256)


def main() -> int:
    try:
        from PIL import Image
        from PySide6.QtCore import QRectF
        from PySide6.QtGui import QImage, QPainter
        from PySide6.QtSvg import QSvgRenderer
    except ImportError as exc:
        print(f"아이콘 build dependency가 없습니다: {exc}", file=sys.stderr)
        return 2
    renderer = QSvgRenderer(str(SOURCE))
    if not renderer.isValid():
        print(f"SVG 아이콘을 읽을 수 없습니다: {SOURCE}", file=sys.stderr)
        return 3
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    png = OUTPUT.with_suffix(".png")
    canvas = QImage(256, 256, QImage.Format.Format_ARGB32)
    canvas.fill(0)
    painter = QPainter(canvas); renderer.render(painter, QRectF(0, 0, 256, 256)); painter.end()
    if not canvas.save(str(png), "PNG"):
        return 4
    with Image.open(png) as image:
        image.save(OUTPUT, format="ICO", sizes=[(size, size) for size in SIZES])
    png.unlink(missing_ok=True)
    if not OUTPUT.is_file() or OUTPUT.stat().st_size == 0:
        return 5
    print(OUTPUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
