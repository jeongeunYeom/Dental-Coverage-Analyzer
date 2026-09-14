from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from enum import Enum
import json
from pathlib import Path
from typing import Any

from dental_coverage_analyzer.core.resources import load_config
from dental_coverage_analyzer.models import (
    AggregateCoverage, Confidence, DentalRider, EffectiveTextSource,
    ExtractionCandidate, InsuranceContract, PDFDocumentData, PDFPageData, PDFWord,
    ParserSupportSummary, SupportLevel, ValidationIssue, ValidationSeverity,
)

from .layout_extractor import extract_page_layout
from .ocr_engine import OCREngine, OCRResult, OCRStatus
from .page_classifier import PageClassifier
from .page_renderer import RenderedPage, render_page_png
from .page_signals import PageSignalDetector
from .pdf_loader import PDFLoader
from .table_layout import build_rows, infer_columns
from .tesseract_ocr import TesseractOCREngine
from .text_quality import TextQualityResult, TextQualityStatus, analyze_text_quality


class AnalysisCancelledError(RuntimeError):
    pass


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
    provider: str = "UNKNOWN"
    provider_confidence: Confidence = Confidence.LOW
    provider_reason: str = "provider 분석 전"
    support_summary: ParserSupportSummary | None = None

    @property
    def total_pages(self) -> int:
        return self.document.total_pages

    def to_dict(self) -> dict[str, Any]:
        return _json_value({
            "file": self.document.file_name, "file_path": self.document.file_path,
            "total_pages": self.document.total_pages, "metadata": self.document.metadata,
            "is_encrypted": self.document.is_encrypted,
            "text_quality_summary": self.text_quality_summary,
            "ocr_required_pages": self.ocr_required_pages,
            "detected_page_types": self.detected_page_types,
            "dental_candidate_pages": self.dental_candidate_pages,
            "insurer_candidates": self.insurer_candidates,
            "product_candidates": self.product_candidates,
            "contracts": self.contracts, "aggregate_coverages": self.aggregate_coverages,
            "dental_riders": self.dental_riders, "validation_issues": self.validation_issues,
            "dental_product_count": self.dental_product_count,
            "provider": self.provider, "provider_confidence": self.provider_confidence,
            "provider_reason": self.provider_reason, "support_summary": self.support_summary,
            "pages": self.document.pages,
        })

    def export_json(self, destination: str | Path) -> Path:
        output = Path(destination).expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
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


def _quality_metrics(quality: TextQualityResult) -> dict[str, Any]:
    return {
        "total_characters": quality.total_characters, "hangul_ratio": quality.hangul_ratio,
        "digit_ratio": quality.digit_ratio, "meaningful_word_count": quality.meaningful_word_count,
        "insurance_term_count": quality.insurance_term_count,
        "insurance_term_rate": quality.insurance_term_rate,
        "broken_character_ratio": quality.broken_character_ratio,
        "odd_spacing_ratio": quality.odd_spacing_ratio, "reasons": list(quality.reasons),
    }


def _quality_rank(quality: TextQualityResult) -> tuple[int, int, float]:
    rank = {
        TextQualityStatus.IMAGE_ONLY: 0, TextQualityStatus.TEXT_GARBLED: 1,
        TextQualityStatus.TEXT_PARTIAL: 2, TextQualityStatus.TEXT_OK: 3,
    }[quality.status]
    return rank, quality.insurance_term_count, quality.hangul_ratio


def _semantic_terms(text: str) -> set[str]:
    important = {
        "보험", "가입", "보장", "담보", "치아", "치과", "보철", "보존", "발치",
        "근관", "치수", "치주", "스케일링", "파노라마", "상품명", "보험회사",
    }
    compact = "".join(text.split())
    return {term for term in important if term in compact}


def _ocr_words_to_pdf(result: OCRResult, rendered: RenderedPage, page: PDFPageData) -> list[PDFWord]:
    x_scale = page.width / rendered.width
    y_scale = page.height / rendered.height
    return [
        PDFWord(
            word.text, word.bbox[0] * x_scale, word.bbox[1] * y_scale,
            word.bbox[2] * x_scale, word.bbox[3] * y_scale,
            word.block_no, word.line_no, word.word_no,
        )
        for word in result.words
    ]


def apply_ocr_result(
    page: PDFPageData,
    rendered: RenderedPage,
    result: OCRResult,
    original_quality: TextQualityResult,
    settings: dict[str, Any],
) -> list[ValidationIssue]:
    """OCR provenance를 보존하고 evidence에 따라 effective text를 선택한다."""
    page.ocr_status = result.status.value
    page.ocr_confidence = result.confidence
    page.ocr_reason = result.reason
    issues: list[ValidationIssue] = []
    if result.status is OCRStatus.NOT_CONFIGURED:
        return issues
    if result.status is OCRStatus.FAILED:
        return issues
    page.ocr_text = result.text or ""
    ocr_quality = analyze_text_quality(page.ocr_text)
    page.ocr_text_quality = ocr_quality.status.value
    ocr_words = _ocr_words_to_pdf(result, rendered, page)
    page.ocr_words = ocr_words
    minimum = float(settings["minimum_confidence"])
    if (result.confidence or 0) < minimum:
        page.confidence = Confidence.LOW
        issues.append(ValidationIssue(
            "LOW_OCR_CONFIDENCE", ValidationSeverity.WARNING,
            f"OCR 평균 confidence가 기준({minimum:g})보다 낮습니다",
            [page.page_number], "PDFPageData", str(page.page_number), [str(result.confidence)],
        ))
    original_terms = _semantic_terms(page.text_layer_text or "")
    ocr_terms = _semantic_terms(page.ocr_text)
    minimum_terms = int(settings["conflict_term_minimum"])
    conflict = (
        len(original_terms) >= minimum_terms and len(ocr_terms) >= minimum_terms
        and len(original_terms & ocr_terms) / len(original_terms | ocr_terms)
        < float(settings["conflict_similarity"])
    )
    if conflict:
        merged = f"{page.text_layer_text or ''}\n{page.ocr_text}".strip()
        page.use_effective_text(merged, EffectiveTextSource.MERGED, ocr_words)
        page.effective_text_quality = analyze_text_quality(merged).status.value
        page.confidence = Confidence.LOW
        issues.append(ValidationIssue(
            "TEXT_OCR_CONFLICT", ValidationSeverity.WARNING,
            "Text Layer와 OCR의 핵심 보험 용어가 크게 충돌합니다",
            [page.page_number], "PDFPageData", str(page.page_number),
            [", ".join(sorted(original_terms)), ", ".join(sorted(ocr_terms))],
        ))
    elif _quality_rank(ocr_quality) > _quality_rank(original_quality):
        page.use_effective_text(page.ocr_text, EffectiveTextSource.OCR, ocr_words)
        page.effective_text_quality = ocr_quality.status.value
        page.confidence = (
            Confidence.MEDIUM if (result.confidence or 0) >= minimum else Confidence.LOW
        )
    else:
        page.effective_text_quality = original_quality.status.value
    return issues


def _deduplicate_candidates(candidates: list[ExtractionCandidate]) -> list[ExtractionCandidate]:
    seen: set[tuple[str, int]] = set()
    result = []
    for candidate in candidates:
        key = candidate.value, candidate.page_number
        if key not in seen:
            seen.add(key)
            result.append(candidate)
    return result


def _support_level(provider: str, extracted: int, issues: int, failed_ocr: int) -> SupportLevel:
    if extracted == 0 and provider == "UNKNOWN":
        return SupportLevel.UNSUPPORTED
    if failed_ocr or issues:
        return SupportLevel.REVIEW_REQUIRED
    if provider in {"UNKNOWN", "GENERIC"}:
        return SupportLevel.PARTIAL
    return SupportLevel.FULL


def analyze_pdf(
    path: str | Path,
    *,
    password: str | None = None,
    classifier: PageClassifier | None = None,
    signal_detector: PageSignalDetector | None = None,
    ocr_engine: OCREngine | None = None,
    on_progress: Callable[[int, int, str], None] | None = None,
    is_cancelled: Callable[[], bool] | None = None,
) -> PDFAnalysisResult:
    """외부 통신 없이 Text Layer → 선택적 local OCR → parser pipeline을 실행한다."""
    classifier = classifier or PageClassifier()
    signal_detector = signal_detector or PageSignalDetector()
    ocr_engine = ocr_engine or TesseractOCREngine()
    settings = load_config("ocr_settings.json")
    ocr_issues: list[ValidationIssue] = []
    with PDFLoader(path, password=password) as loader:
        document_data = loader.open()
        total = document_data.total_pages
        for page_number in range(1, total + 1):
            if is_cancelled and is_cancelled():
                raise AnalysisCancelledError("PDF 분석이 취소되었습니다")
            if on_progress:
                on_progress(page_number, total, "TEXT_LAYER")
            pdf_page = loader.get_page(page_number)
            page_data = extract_page_layout(pdf_page, page_number)
            original_quality = analyze_text_quality(page_data.text_layer_text)
            page_data.text_quality = original_quality.status.value
            page_data.effective_text_quality = original_quality.status.value
            page_data.text_quality_metrics = _quality_metrics(original_quality)
            page_data.ocr_required = original_quality.ocr_required
            if original_quality.ocr_required:
                if on_progress:
                    on_progress(page_number, total, "OCR")
                try:
                    rendered = render_page_png(pdf_page, int(settings["dpi"]), int(settings["max_pixels"]))
                    ocr_result = ocr_engine.recognize(rendered.png_bytes)
                except (RuntimeError, OSError, ValueError, MemoryError) as exc:
                    rendered = RenderedPage(b"", 1, 1, int(settings["dpi"]))
                    ocr_result = OCRResult(OCRStatus.FAILED, reason=f"OCR 렌더링/실행 실패: {exc}")
                ocr_issues.extend(apply_ocr_result(page_data, rendered, ocr_result, original_quality, settings))
                del rendered

            effective = page_data.effective_text or page_data.text
            classification = classifier.classify(effective)
            keywords, dental_score = signal_detector.dental_signals(effective)
            page_data.page_type = classification.page_type
            page_data.page_type_scores = classification.scores
            page_data.detected_keywords = keywords
            page_data.dental_candidate_score = dental_score
            page_data.insurer_candidates = signal_detector.insurer_candidates(
                effective, page_data.effective_words, page_number,
            )
            page_data.product_candidates = signal_detector.product_candidates(
                effective, page_data.effective_words, page_number,
            )
            if page_data.effective_source is EffectiveTextSource.TEXT_LAYER:
                page_data.confidence = Confidence.LOW if original_quality.ocr_required else classification.confidence
            page_data.confidence_reason = (
                f"effective source={page_data.effective_source.value}; {classification.reason}"
            )
            rows = build_rows(page_data.effective_words, page_data.height)
            columns = infer_columns(rows)
            page_data.row_reconstruction_summary = {
                "row_count": len(rows), "column_candidate_count": len(columns),
                "rows": [{"text": row.text, "bbox": row.bbox} for row in rows],
                "column_candidates": [
                    {"x_center": column.x_center, "word_count": column.word_count}
                    for column in columns
                ],
            }
            document_data.pages.append(page_data)

    from dental_coverage_analyzer.core.parsers import GenericParser
    from dental_coverage_analyzer.core.parsers.provider_detector import ProviderDetector

    if is_cancelled and is_cancelled():
        raise AnalysisCancelledError("PDF 분석이 취소되었습니다")
    if on_progress:
        on_progress(document_data.total_pages, document_data.total_pages, "PARSING")
    provider = ProviderDetector().detect(document_data)
    parser = GenericParser()
    parsed = parser.parse(document_data, provider.provider)
    all_issues = [*ocr_issues, *parsed.validation_issues]
    if provider.confidence is Confidence.LOW:
        all_issues.append(ValidationIssue(
            "PROVIDER_UNCERTAIN", ValidationSeverity.WARNING, provider.reason,
            related_object_type="PDFDocumentData",
        ))
    quality_counts = Counter(page.text_quality for page in document_data.pages)
    type_counts = Counter(page.page_type.value for page in document_data.pages)
    insurers = _deduplicate_candidates([item for page in document_data.pages for item in page.insurer_candidates])
    products = _deduplicate_candidates([item for page in document_data.pages for item in page.product_candidates])
    attempted = [page for page in document_data.pages if page.ocr_status != "NOT_ATTEMPTED"]
    success = [page for page in attempted if page.ocr_status == "SUCCESS"]
    failed = [page for page in attempted if page.ocr_status in {"FAILED", "NOT_CONFIGURED"}]
    extracted = len(parsed.contracts) + len(parsed.aggregate_coverages) + len(parsed.dental_riders)
    support = ParserSupportSummary(
        provider.provider.value, provider.confidence, provider.reason,
        sum(bool((page.text_layer_text or "").strip()) for page in document_data.pages),
        len(attempted), len(success), len(failed), len(parsed.contracts),
        len(parsed.aggregate_coverages), len(parsed.dental_riders), len(all_issues),
        _support_level(provider.provider.value, extracted, len(all_issues), len(failed)),
    )
    return PDFAnalysisResult(
        document_data, dict(quality_counts),
        [page.page_number for page in document_data.pages if page.ocr_required],
        dict(type_counts),
        [page.page_number for page in document_data.pages if page.dental_candidate_score > 0],
        insurers, products, parsed.contracts, parsed.aggregate_coverages,
        parsed.dental_riders, all_issues, parser.dental_contract_count(parsed.contracts),
        provider.provider.value, provider.confidence, provider.reason, support,
    )
