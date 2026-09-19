from pathlib import Path
import sys

from dental_coverage_analyzer.core.pdf.ocr_health import OCRAvailability, check_ocr_availability
from dental_coverage_analyzer.core.pdf.tesseract_ocr import TesseractOCREngine


def test_frozen_bundle_is_resolved_before_explicit_and_path(tmp_path, monkeypatch):
    bundle = tmp_path / "frozen app" / "tesseract"
    bundle.mkdir(parents=True)
    executable = bundle / ("tesseract.exe" if __import__("os").name == "nt" else "tesseract")
    executable.write_bytes(b"bundled")
    explicit = tmp_path / "explicit"; explicit.write_bytes(b"external")
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle.parent), raising=False)
    assert TesseractOCREngine(explicit)._resolve() == executable


def test_health_reports_broken_when_language_data_is_missing(tmp_path, monkeypatch):
    bundle = tmp_path / "tesseract"; bundle.mkdir()
    executable = bundle / ("tesseract.exe" if __import__("os").name == "nt" else "tesseract")
    executable.write_bytes(b"binary")
    monkeypatch.setattr(TesseractOCREngine, "_resolve", lambda self: executable)
    health = check_ocr_availability(require_bundled=True)
    assert health.status is OCRAvailability.BROKEN
    assert "eng.traineddata" in health.reason and "kor.traineddata" in health.reason


def test_health_check_command_reports_success(monkeypatch, capsys):
    import dental_coverage_analyzer.gui_main as gui_main
    from dental_coverage_analyzer.core.pdf.ocr_health import OCRHealth

    monkeypatch.setattr(gui_main, "load_config", lambda _name: {})
    monkeypatch.setattr(
        gui_main, "check_ocr_availability",
        lambda **_kwargs: OCRHealth(OCRAvailability.AVAILABLE, Path("tesseract/tesseract.exe")),
    )
    assert gui_main.health_check() == 0
    assert capsys.readouterr().out.splitlines() == ["APP_OK", "OCR_OK"]
