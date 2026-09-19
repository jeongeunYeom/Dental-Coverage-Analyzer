from __future__ import annotations

from dataclasses import dataclass, field
from typing import Generic, Protocol, TypeVar

from dental_coverage_analyzer.models import PDFDocumentData, ValidationIssue


T = TypeVar("T")


@dataclass(slots=True)
class ParserOutput(Generic[T]):
    items: list[T] = field(default_factory=list)
    issues: list[ValidationIssue] = field(default_factory=list)


class DocumentParser(Protocol[T]):
    def parse(self, document: PDFDocumentData) -> ParserOutput[T]: ...
