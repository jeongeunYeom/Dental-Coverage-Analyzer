from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

from .common import Confidence


class PageType(StrEnum):
    COVER = "COVER"
    SUMMARY = "SUMMARY"
    ONE_PAGE_SUMMARY = "ONE_PAGE_SUMMARY"
    CONTRACT_LIST = "CONTRACT_LIST"
    COVERAGE_ANALYSIS = "COVERAGE_ANALYSIS"
    COVERAGE_DETAIL = "COVERAGE_DETAIL"
    PRODUCT_MATRIX = "PRODUCT_MATRIX"
    PRODUCT_DETAIL = "PRODUCT_DETAIL"
    DIAGNOSIS_DETAIL = "DIAGNOSIS_DETAIL"
    NOTICE = "NOTICE"
    GRAPH = "GRAPH"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class PDFWord:
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    block_no: int
    line_no: int
    word_no: int

    @property
    def bbox(self) -> tuple[float, float, float, float]:
        return self.x0, self.y0, self.x1, self.y1


@dataclass(frozen=True, slots=True)
class PDFBlock:
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    block_no: int
    block_type: int = 0

    @property
    def bbox(self) -> tuple[float, float, float, float]:
        return self.x0, self.y0, self.x1, self.y1


@dataclass(frozen=True, slots=True)
class ExtractionCandidate:
    value: str
    page_number: int
    bbox: tuple[float, float, float, float] | None
    confidence: Confidence
    confidence_reason: str


@dataclass(slots=True)
class PDFPageData:
    page_number: int
    width: float
    height: float
    text: str
    words: list[PDFWord] = field(default_factory=list)
    blocks: list[PDFBlock] = field(default_factory=list)
    text_quality: str = "IMAGE_ONLY"
    text_quality_metrics: dict[str, Any] = field(default_factory=dict)
    ocr_required: bool = True
    page_type: PageType = PageType.UNKNOWN
    page_type_scores: dict[str, float] = field(default_factory=dict)
    detected_keywords: list[str] = field(default_factory=list)
    dental_candidate_score: float = 0.0
    insurer_candidates: list[ExtractionCandidate] = field(default_factory=list)
    product_candidates: list[ExtractionCandidate] = field(default_factory=list)
    confidence: Confidence = Confidence.LOW
    confidence_reason: str = "페이지 분석 전"


@dataclass(slots=True)
class PDFDocumentData:
    file_path: Path
    file_name: str
    total_pages: int
    metadata: dict[str, str | None]
    is_encrypted: bool
    pages: list[PDFPageData] = field(default_factory=list)

