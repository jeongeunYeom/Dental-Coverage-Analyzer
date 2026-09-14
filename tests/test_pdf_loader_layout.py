from pathlib import Path

import pytest

from dental_coverage_analyzer.core.pdf.layout_extractor import extract_page_layout
from dental_coverage_analyzer.core.pdf.pdf_loader import (
    PDFLoadError,
    PDFLoader,
    PDFPasswordRequiredError,
)


def test_loader_returns_metadata_and_one_based_pages(synthetic_pdf: Path):
    with PDFLoader(synthetic_pdf) as loader:
        data = loader.open()
        assert data.total_pages == 2
        assert data.file_name == "synthetic.pdf"
        assert data.metadata["title"] == "Synthetic test document"
        assert data.is_encrypted is False
        assert loader.get_page(1).number == 0
        with pytest.raises(IndexError):
            loader.get_page(0)


def test_loader_wraps_missing_or_corrupt_files(tmp_path: Path):
    with pytest.raises(PDFLoadError):
        PDFLoader(tmp_path / "missing.pdf").open()
    bad = tmp_path / "bad.pdf"
    bad.write_text("not a pdf", encoding="utf-8")
    with pytest.raises(PDFLoadError):
        PDFLoader(bad).open()


def test_loader_reports_encryption_and_authenticates(tmp_path: Path):
    fitz = pytest.importorskip("fitz", reason="PyMuPDF가 필요한 암호화 PDF 테스트")
    path = tmp_path / "encrypted.pdf"
    document = fitz.open()
    document.new_page().insert_text((40, 50), "Synthetic encrypted page")
    document.save(
        path,
        encryption=fitz.PDF_ENCRYPT_AES_256,
        owner_pw="owner-synthetic",
        user_pw="user-synthetic",
    )
    document.close()

    with pytest.raises(PDFPasswordRequiredError):
        PDFLoader(path).open()
    with PDFLoader(path, password="user-synthetic") as loader:
        data = loader.open()
        assert data.is_encrypted is True
        assert data.total_pages == 1


def test_layout_extractor_preserves_words_blocks_and_dimensions(synthetic_pdf: Path):
    with PDFLoader(synthetic_pdf) as loader:
        loader.open()
        page = extract_page_layout(loader.get_page(1), 1)
    assert page.page_number == 1
    assert page.width == pytest.approx(420)
    assert page.height == pytest.approx(595)
    assert "Synthetic insurance" in page.text
    assert page.words and page.blocks
    word = page.words[0]
    assert word.text == "Synthetic"
    assert word.x1 > word.x0 and word.y1 > word.y0
    assert word.block_no >= 0 and word.line_no >= 0 and word.word_no >= 0
