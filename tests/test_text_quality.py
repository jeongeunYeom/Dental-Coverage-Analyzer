from pathlib import Path

import pytest

from dental_coverage_analyzer.core.pdf.text_quality import TextQualityStatus, analyze_text_quality

FIXTURES = Path(__file__).parent / "fixtures"


def test_normal_insurance_text_is_ok():
    text = (FIXTURES / "meritz_aggregate.txt").read_text(encoding="utf-8")
    result = analyze_text_quality(text)
    assert result.status is TextQualityStatus.TEXT_OK
    assert result.ocr_required is False
    assert result.insurance_term_count >= 2


def test_numeric_dominated_text_is_garbled_and_requires_ocr():
    text = (FIXTURES / "garbled_numeric.txt").read_text(encoding="utf-8")
    result = analyze_text_quality(text)
    assert result.status is TextQualityStatus.TEXT_GARBLED
    assert result.ocr_required is True
    assert result.digit_ratio > 0.55


@pytest.mark.parametrize("text", ["", "   \n", "12"])
def test_empty_or_nearly_empty_layer_is_image_only(text):
    result = analyze_text_quality(text)
    assert result.status is TextQualityStatus.IMAGE_ONLY
    assert result.ocr_required is True


def test_short_but_meaningful_layer_is_partial():
    result = analyze_text_quality("보험 가입금액 50만원")
    assert result.status is TextQualityStatus.TEXT_PARTIAL
    assert result.ocr_required is True


def test_replacement_characters_are_garbled():
    result = analyze_text_quality("보험 가입 보장 " + "�" * 20 + " 100000 200000")
    assert result.status is TextQualityStatus.TEXT_GARBLED
