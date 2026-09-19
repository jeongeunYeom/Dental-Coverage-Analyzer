from pathlib import Path

import pytest


@pytest.fixture
def synthetic_pdf(tmp_path: Path) -> Path:
    """개인정보나 실제 PDF를 포함하지 않는 runtime 생성 문서."""
    fitz = pytest.importorskip("fitz", reason="PyMuPDF가 필요한 통합 테스트")
    path = tmp_path / "synthetic.pdf"
    document = fitz.open()
    first = document.new_page(width=420, height=595)
    first.insert_text((40, 60), "Synthetic insurance coverage analysis")
    first.insert_text((40, 90), "Product name: Local Dental Insurance")
    second = document.new_page(width=500, height=700)
    second.insert_text((50, 80), "167,400 238,500 5,000 30 10,142 200,000 50,000 150,000")
    document.set_metadata({"title": "Synthetic test document", "author": "pytest"})
    document.save(path)
    document.close()
    return path
