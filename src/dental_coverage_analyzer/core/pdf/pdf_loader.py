from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    import fitz
except ImportError:  # dependency availability is reported as a domain error at runtime
    fitz = None  # type: ignore[assignment]

from dental_coverage_analyzer.models import PDFDocumentData


class PDFLoadError(RuntimeError):
    """읽을 수 없거나 손상된 PDF에 대한 안전한 공개 예외."""


class PDFPasswordRequiredError(PDFLoadError):
    """암호가 필요하거나 제공된 암호가 올바르지 않음."""


class PDFLoader:
    """PyMuPDF 문서의 수명과 기본 metadata를 관리한다."""

    def __init__(self, path: str | Path, password: str | None = None) -> None:
        self.path = Path(path).expanduser().resolve()
        self.password = password
        self._document: Any | None = None
        self._was_encrypted = False

    def open(self) -> PDFDocumentData:
        if fitz is None:
            raise PDFLoadError("PyMuPDF가 설치되어 있지 않습니다")
        if not self.path.is_file():
            raise PDFLoadError(f"PDF 파일을 찾을 수 없습니다: {self.path}")
        try:
            document = fitz.open(self.path)
        except (fitz.FileDataError, RuntimeError, ValueError) as exc:
            raise PDFLoadError(f"PDF 파일을 열 수 없습니다: {self.path.name}") from exc

        self._was_encrypted = bool(document.needs_pass or document.is_encrypted)
        if document.needs_pass:
            if not self.password or not document.authenticate(self.password):
                document.close()
                raise PDFPasswordRequiredError("암호화된 PDF이며 올바른 암호가 필요합니다")
        self._document = document
        metadata: dict[str, Any] = document.metadata or {}
        return PDFDocumentData(
            file_path=self.path,
            file_name=self.path.name,
            total_pages=document.page_count,
            metadata={str(key): value for key, value in metadata.items()},
            is_encrypted=self._was_encrypted,
        )

    @property
    def document(self) -> Any:
        if self._document is None or self._document.is_closed:
            raise PDFLoadError("PDF가 열려 있지 않습니다")
        return self._document

    def get_page(self, page_number: int) -> Any:
        """사용자 표시와 동일한 1-base 페이지 번호로 접근한다."""
        if not 1 <= page_number <= self.document.page_count:
            raise IndexError(f"페이지 번호 범위 오류: {page_number}")
        return self.document.load_page(page_number - 1)

    def close(self) -> None:
        if self._document is not None and not self._document.is_closed:
            self._document.close()

    def __enter__(self) -> PDFLoader:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
