import os
from pathlib import Path

import pytest

from dental_coverage_analyzer.core.pdf import OCRStatus
from dental_coverage_analyzer.core.pdf.tesseract_ocr import TesseractOCREngine


@pytest.mark.skipif(os.environ.get("DCA_BUNDLED_OCR_TEST") != "1", reason="Windows release bundle test")
def test_real_bundled_tesseract_loads_korean_and_english_and_recognizes_text(monkeypatch):
    pytest.importorskip("PySide6")
    try:
        from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Qt
        from PySide6.QtGui import QColor, QFont, QImage, QPainter
    except ImportError as exc:
        pytest.skip(f"Qt system library unavailable: {exc}")
    root = Path(os.environ["DCA_TESSERACT_ROOT"])
    executable = root / "tesseract.exe"
    assert executable.is_file()
    assert (root / "tessdata/kor.traineddata").is_file()
    assert (root / "tessdata/eng.traineddata").is_file()

    image = QImage(900, 180, QImage.Format.Format_RGB32)
    image.fill(QColor("white"))
    painter = QPainter(image)
    painter.setPen(QColor("black")); painter.setFont(QFont("Malgun Gothic", 32))
    painter.drawText(image.rect(), Qt.AlignmentFlag.AlignCenter, "Dental 200 치아")
    painter.end()
    payload = QByteArray(); buffer = QBuffer(payload); buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    assert image.save(buffer, "PNG")

    result = TesseractOCREngine(executable).recognize(bytes(payload), ("kor", "eng"))
    assert result.status is OCRStatus.SUCCESS
    assert result.text.strip()
