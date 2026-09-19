import io
import os
from pathlib import Path
import subprocess

import pytest

from dental_coverage_analyzer.core.pdf import OCRStatus
from dental_coverage_analyzer.core.pdf.tesseract_ocr import TesseractOCREngine


@pytest.mark.skipif(os.environ.get("DCA_BUNDLED_OCR_TEST") != "1", reason="Windows release bundle test")
def test_real_bundled_tesseract_loads_korean_and_english_and_recognizes_text():
    from PIL import Image, ImageDraw, ImageFont

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

    font_candidates = (
        Path(r"C:\Windows\Fonts\arial.ttf"),
        Path(r"C:\Windows\Fonts\segoeui.ttf"),
        Path(r"C:\Windows\Fonts\calibri.ttf"),
    )
    font_path = next((candidate for candidate in font_candidates if candidate.is_file()), None)
    assert font_path is not None, f"No stable Windows TrueType font found: {font_candidates}"
    font = ImageFont.truetype(str(font_path), 80)

    test_text = "DENTAL COVERAGE ANALYSIS\nDENTAL INSURANCE 2000000\nDENTAL COVERAGE 500000"
    image = Image.new("RGB", (1600, 700), "white")
    ImageDraw.Draw(image).multiline_text(
        (100, 100), test_text, fill="black", font=font, spacing=70,
    )
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    payload = buffer.getvalue()
    assert payload.startswith(b"\x89PNG\r\n\x1a\n")

    result = TesseractOCREngine(executable).recognize(bytes(payload), ("kor", "eng"))
    print(f"OCR status: {result.status}")
    print(f"OCR reason: {result.reason}")
    assert result.status is OCRStatus.SUCCESS, result.reason
    assert result.text.strip(), "bundled OCR returned empty text"
    assert "DENTAL" in result.text.upper()
