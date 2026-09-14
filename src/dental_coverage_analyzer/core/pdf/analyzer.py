from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field
from enum import Enum
import json
from pathlib import Path
from typing import Any

from dental_coverage_analyzer.models import (
    AggregateCoverage,
    Confidence,
    DentalRider,
    ExtractionCandidate,
    InsuranceContract,
    PDFDocumentData,
    ValidationIssue,
)

from .layout_extractor import extract_page_layout
from .page_classifier import PageClassifier
from .page_signals import PageSignalDetector
from .pdf_loader import PDFLoader
from .text_quality import analyze_text_quality


@dataclass(slots=True)
class PDFAnalysisResult:
    document: PDFDocumentData
    text_quality_summary: dict[str, int]
    ocr_required_pages: list[int]
    detected_page_types: dict[str, int]
    dental_candidate_pages: list[int]
    insurer_candidates: list[ExtractionCandidate]
    product_candidates: list[ExtractionCandidate]
    contracts: list[InsuranceContract] = field(default_factory=list)
    aggregate_coverages: list[AggregateCoverage] = field(default_factory=list)
    dental_riders: list[DentalRider] = field(default_factory=list)
    validation_issues: list[ValidationIssue] = field(default_factory=list)
    dental_product_count: int = 0

    @property
    def total_pages(self) -> int:
        return self.document.total_pages

    def to_dict(self) -> dict[str, Any]:
        return _json_value({
            "file": self.document.file_name,
            "file_path": self.document.file_path,
            "total_pages": self.document.total_pages,
            "metadata": self.document.metadata,
            "is_encrypted": self.document.is_encrypted,
            "text_quality_summary": self.text_quality_summary,
            "ocr_required_pages": self.ocr_required_pages,
            "detected_page_types": self.detected_page_types,
            "dental_candidate_pages": self.dental_candidate_pages,
            "insurer_candidates": self.insurer_candidates,
            "product_candidates": self.product_candidates,
            "contracts": self.contracts,
            "aggregate_coverages": self.aggregate_coverages,
            "dental_riders": self.dental_riders,
            "validation_issues": self.validation_issues,
            "dental_product_count": self.dental_product_count,
            "pages": self.document.pages,
        })

    def export_json(self, destination: str | Path) -> Path:
        """분석 결과를 지정한 로컬 파일에 UTF-8 JSON으로 저장한다."""
        output = Path(destination).expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return output


def _json_value(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        return {key: _json_value(item) for key, item in asdict(value).items()}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


def _deduplicate_candidates(candidates: list[ExtractionCandidate]) -> list[ExtractionCandidate]:
    seen: set[tuple[str, int]] = set()
    result = []
    for candidate in candidates:
        key = (candidate.value, candidate.page_number)
        if key not in seen:
            seen.add(key)
            result.append(candidate)
    return result


def analyze_pdf(
    path: str | Path,
    *,
    password: str | None = None,
    classifier: PageClassifier | None = None,
    signal_detector: PageSignalDetector | None = None,
) -> PDFAnalysisResult:
    """PDF를 페이지 단위 구조화 데이터로 변환한다. 외부 통신은 수행하지 않는다."""
    classifier = classifier or PageClassifier()
    signal_detector = signal_detector or PageSignalDetector()
    with PDFLoader(path, password=password) as loader:
        document_data = loader.open()
        for page_number in range(1, document_data.total_pages + 1):
            page_data = extract_page_layout(loader.get_page(page_number), page_number)
            quality = analyze_text_quality(page_data.text)
            classification = classifier.classify(page_data.text)
            keywords, dental_score = signal_detector.dental_signals(page_data.text)

            page_data.text_quality = quality.status.value
            page_data.text_quality_metrics = {
                "total_characters": quality.total_characters,
                "hangul_ratio": quality.hangul_ratio,
                "digit_ratio": quality.digit_ratio,
                "meaningful_word_count": quality.meaningful_word_count,
                "insurance_term_count": quality.insurance_term_count,
                "insurance_term_rate": quality.insurance_term_rate,
                "broken_character_ratio": quality.broken_character_ratio,
                "odd_spacing_ratio": quality.odd_spacing_ratio,
                "reasons": list(quality.reasons),
            }
            page_data.ocr_required = quality.ocr_required
            page_data.page_type = classification.page_type
            page_data.page_type_scores = classification.scores
            page_data.detected_keywords = keywords
            page_data.dental_candidate_score = dental_score
            page_data.insurer_candidates = signal_detector.insurer_candidates(
                page_data.text, page_data.words, page_number,
            )
            page_data.product_candidates = signal_detector.product_candidates(
                page_data.text, page_data.words, page_number,
            )
            page_data.confidence = (
                Confidence.LOW if quality.ocr_required else classification.confidence
            )
            page_data.confidence_reason = (
                "; ".join(quality.reasons) if quality.ocr_required else classification.reason
            )
            document_data.pages.append(page_data)

    quality_counts = Counter(page.text_quality for page in document_data.pages)
    type_counts = Counter(page.page_type.value for page in document_data.pages)
    insurers = _deduplicate_candidates([
        candidate for page in document_data.pages for candidate in page.insurer_candidates
    ])
    products = _deduplicate_candidates([
        candidate for page in document_data.pages for candidate in page.product_candidates
    ])
    # 지연 import로 PDF foundation과 parser의 모듈 의존 방향을 단순하게 유지한다.
    from dental_coverage_analyzer.core.parsers import GenericParser

    parser = GenericParser()
    parsed = parser.parse(document_data)
    return PDFAnalysisResult(
        document=document_data,
        text_quality_summary=dict(quality_counts),
        ocr_required_pages=[page.page_number for page in document_data.pages if page.ocr_required],
        detected_page_types=dict(type_counts),
        dental_candidate_pages=[
            page.page_number for page in document_data.pages if page.dental_candidate_score > 0
        ],
        insurer_candidates=insurers,
        product_candidates=products,
        contracts=parsed.contracts,
        aggregate_coverages=parsed.aggregate_coverages,
        dental_riders=parsed.dental_riders,
        validation_issues=parsed.validation_issues,
        dental_product_count=parser.dental_contract_count(parsed.contracts),
    )
