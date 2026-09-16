from __future__ import annotations

from typing import Protocol

from dental_coverage_analyzer.models import PDFDocumentData


class ProviderAdapter(Protocol):
    """GenericParser 입력에 근거 기반 hint만 추가한다."""

    def apply_hints(self, document: PDFDocumentData) -> None: ...

