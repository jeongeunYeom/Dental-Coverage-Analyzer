from pathlib import Path

from dental_coverage_analyzer.core.pdf.ocr_engine import OCRStatus
from dental_coverage_analyzer.core.pdf.tesseract_ocr import TesseractOCREngine


def test_tesseract_not_found_is_not_configured(monkeypatch):
    engine = TesseractOCREngine("/definitely/missing/tesseract")
    monkeypatch.setattr("shutil.which", lambda _name: None)
    result = engine.recognize(b"png")
    assert result.status is OCRStatus.NOT_CONFIGURED


def test_tesseract_tsv_is_converted_without_network(monkeypatch, tmp_path: Path):
    executable = tmp_path / "tesseract"
    executable.write_text("synthetic", encoding="utf-8")
    tsv = (
        "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
        "5\t1\t1\t1\t1\t1\t10\t20\t50\t15\t91.5\t치아보험\n"
    )
    class Process:
        returncode = 0
        stdout = tsv
        stderr = ""
    monkeypatch.setattr("subprocess.run", lambda *_args, **_kwargs: Process())
    result = TesseractOCREngine(executable).recognize(b"fake-png")
    assert result.status is OCRStatus.SUCCESS
    assert result.text == "치아보험"
    assert result.confidence == 91.5
    assert result.words[0].bbox == (10, 20, 60, 35)

