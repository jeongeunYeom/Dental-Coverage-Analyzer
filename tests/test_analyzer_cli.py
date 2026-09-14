import json
from pathlib import Path

from dental_coverage_analyzer.__main__ import main
from dental_coverage_analyzer.core.pdf.analyzer import PDFAnalysisResult, analyze_pdf
from dental_coverage_analyzer.models import PDFDocumentData, PDFPageData


def test_json_export_schema_without_pdf_dependency(tmp_path: Path):
    page = PDFPageData(1, 100, 200, "합성 텍스트", text_quality="TEXT_PARTIAL")
    document = PDFDocumentData(
        tmp_path / "synthetic.pdf", "synthetic.pdf", 1, {"title": "Synthetic"}, False, [page]
    )
    result = PDFAnalysisResult(
        document, {"TEXT_PARTIAL": 1}, [1], {"UNKNOWN": 1}, [], [], [],
    )
    payload = json.loads(result.export_json(tmp_path / "debug.json").read_text(encoding="utf-8"))
    assert payload["file"] == "synthetic.pdf"
    assert payload["total_pages"] == 1
    assert payload["pages"][0]["text_quality"] == "TEXT_PARTIAL"


def test_analyzer_structures_all_pages_and_exports_json(synthetic_pdf: Path, tmp_path: Path):
    result = analyze_pdf(synthetic_pdf)
    assert result.total_pages == 2
    assert len(result.document.pages) == 2
    assert result.document.pages[0].words
    assert result.document.pages[1].ocr_required is True
    assert 2 in result.ocr_required_pages

    output = result.export_json(tmp_path / "analysis.json")
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["file"] == "synthetic.pdf"
    assert payload["total_pages"] == 2
    assert payload["pages"][0]["words"][0]["text"] == "Synthetic"
    assert payload["ocr_required_pages"] == result.ocr_required_pages


def test_cli_prints_summary_and_writes_json(synthetic_pdf: Path, tmp_path: Path, capsys):
    output = tmp_path / "cli.json"
    assert main(["analyze", str(synthetic_pdf), "--json", str(output)]) == 0
    stdout = capsys.readouterr().out
    assert "총 페이지 수: 2" in stdout
    assert "OCR 필요 페이지:" in stdout
    assert "페이지 유형:" in stdout
    assert output.is_file()


def test_cli_handles_missing_pdf_without_traceback(tmp_path: Path, capsys):
    assert main(["analyze", str(tmp_path / "missing.pdf")]) == 2
    assert "분석 실패:" in capsys.readouterr().out
