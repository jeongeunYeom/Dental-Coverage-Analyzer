import os
from pathlib import Path
import subprocess

import pytest

from dental_coverage_analyzer.core.pdf import OCRStatus
from dental_coverage_analyzer.core.pdf.tesseract_ocr import TesseractOCREngine


@pytest.mark.skipif(os.environ.get("DCA_BUNDLED_OCR_TEST") != "1", reason="Windows release bundle test")
def test_real_bundled_tesseract_loads_korean_and_english_and_recognizes_text(monkeypatch):
    pytest.importorskip("PySide6")
    try:
        from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Qt
        from PySide6.QtGui import QColor, QFont, QFontDatabase, QGuiApplication, QImage, QPainter
    except ImportError as exc:
        pytest.skip(f"Qt system library unavailable: {exc}")
    root = Path(os.environ["DCA_TESSERACT_ROOT"])
    executable = root / "tesseract.exe"
    tessdata = root / "tessdata"
    assert executable.is_file(), f"bundled executable missing: {executable}"
    assert (tessdata / "kor.traineddata").is_file(), f"Korean model missing: {tessdata}"
    assert (tessdata / "eng.traineddata").is_file(), f"English model missing: {tessdata}"

    environment = os.environ.copy()
    environment["TESSDATA_PREFIX"] = str(tessdata)
    version = subprocess.run(
        [str(executable), "--version"], capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=30, check=False, env=environment,
    )
    languages = subprocess.run(
        [str(executable), "--tessdata-dir", str(tessdata), "--list-langs"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=30, check=False, env=environment,
    )
    print(f"Tesseract executable: {executable}")
    print(f"Tessdata directory: {tessdata}")
    print(f"Tesseract version:\n{version.stdout or version.stderr}")
    print(f"Tesseract languages:\n{languages.stdout or languages.stderr}")
    assert version.returncode == 0, version.stderr
    assert languages.returncode == 0, languages.stderr
    loaded_languages = {line.strip() for line in languages.stdout.splitlines()}
    assert {"kor", "eng"} <= loaded_languages

    # QFont/QFontDatabase require a live GUI application on Windows. Keep a
    # strong reference until all painting and image serialization are complete.
    gui_application = QGuiApplication.instance() or QGuiApplication([])
    families = set(QFontDatabase.families())
    font_family = next(
        (candidate for candidate in ("Malgun Gothic", "Segoe UI", "Arial") if candidate in families),
        QFont().family(),
    )

    image = QImage(900, 180, QImage.Format.Format_RGB32)
    image.fill(QColor("white"))
    painter = QPainter(image)
    painter.setPen(QColor("black")); painter.setFont(QFont(font_family, 32))
    painter.drawText(image.rect(), Qt.AlignmentFlag.AlignCenter, "Dental 200 치아")
    painter.end()
    payload = QByteArray(); buffer = QBuffer(payload); buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    assert image.save(buffer, "PNG")
    buffer.close()

    result = TesseractOCREngine(executable).recognize(bytes(payload), ("kor", "eng"))
    print(f"OCR status: {result.status}")
    print(f"OCR reason: {result.reason}")
    assert result.status is OCRStatus.SUCCESS, result.reason
    assert result.text.strip(), "bundled OCR returned empty text"
    assert gui_application is not None
