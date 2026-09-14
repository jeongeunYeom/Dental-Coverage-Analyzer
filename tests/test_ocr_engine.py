from dental_coverage_analyzer.core.pdf.ocr_engine import NotConfiguredOCREngine, OCRStatus


def test_unconfigured_local_ocr_is_safe_and_explicit():
    result = NotConfiguredOCREngine().recognize(b"synthetic image")
    assert result.status is OCRStatus.NOT_CONFIGURED
    assert result.text is None
    assert result.confidence is None
    assert "로컬 OCR" in result.reason
