from pathlib import Path

from dental_coverage_analyzer.core.pdf.analyzer import apply_ocr_result
from dental_coverage_analyzer.core.pdf.ocr_engine import OCRResult, OCRStatus, OCRWord
from dental_coverage_analyzer.core.pdf.page_renderer import RenderedPage
from dental_coverage_analyzer.core.pdf.text_quality import analyze_text_quality
from dental_coverage_analyzer.models import EffectiveTextSource, PDFPageData


SETTINGS = {"minimum_confidence": 65, "conflict_term_minimum": 2, "conflict_similarity": 0.25}
RENDERED = RenderedPage(b"png", 1000, 2000, 250)


def page(text: str) -> PDFPageData:
    return PDFPageData(1, 500, 1000, text, text_quality="TEXT_GARBLED", ocr_required=True)


def test_successful_ocr_preserves_text_layer_and_uses_better_text():
    item = page("167,400 238,500 5,000 30 10,142 200000 300000 400000")
    ocr_text = "보험회사 라이나생명 상품명 합성 치아보험 보장 담보 가입금액 컴퍼짓레진 9만원"
    result = OCRResult(
        OCRStatus.SUCCESS, ocr_text, 92.0,
        words=(OCRWord("컴퍼짓레진", (100, 200, 300, 240), 94, 1, 1, 1),),
    )
    issues = apply_ocr_result(item, RENDERED, result, analyze_text_quality(item.text), SETTINGS)
    assert issues == []
    assert item.text_layer_text.startswith("167,400")
    assert item.text.startswith("167,400")
    assert item.ocr_text == ocr_text
    assert item.effective_text == ocr_text
    assert item.effective_source is EffectiveTextSource.OCR
    assert item.ocr_words[0].bbox == (50.0, 100.0, 150.0, 120.0)


def test_low_confidence_ocr_never_becomes_high_confidence():
    item = page("")
    result = OCRResult(OCRStatus.SUCCESS, "보험 치아 보장 가입 담보 컴퍼짓레진 9만원", 40.0)
    issues = apply_ocr_result(item, RENDERED, result, analyze_text_quality(""), SETTINGS)
    assert item.confidence == "LOW"
    assert any(issue.code == "LOW_OCR_CONFIDENCE" for issue in issues)


def test_text_ocr_conflict_is_not_silently_resolved():
    original = "보험 가입 보장 계약 보험료 안내 내용입니다 충분한 원본 문맥입니다"
    item = page(original)
    ocr = "치아 치과 발치 근관 치수 치주 스케일링 상세 치료 내역입니다"
    issues = apply_ocr_result(item, RENDERED, OCRResult(OCRStatus.SUCCESS, ocr, 90), analyze_text_quality(original), SETTINGS)
    assert item.effective_source is EffectiveTextSource.MERGED
    assert original in item.effective_text and ocr in item.effective_text
    assert any(issue.code == "TEXT_OCR_CONFLICT" for issue in issues)


def test_failed_and_unconfigured_results_are_explicit_and_safe():
    for status in (OCRStatus.FAILED, OCRStatus.NOT_CONFIGURED):
        item = page("")
        assert apply_ocr_result(
            item, RENDERED, OCRResult(status, reason="synthetic"), analyze_text_quality(""), SETTINGS,
        ) == []
        assert item.ocr_status == status.value
        assert item.effective_source is EffectiveTextSource.TEXT_LAYER
