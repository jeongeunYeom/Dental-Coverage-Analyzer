from dental_coverage_analyzer.core.parsers.generic_parser import GenericParser
from dental_coverage_analyzer.models import PDFDocumentData, PDFPageData, PageType, ValidationSeverity


def test_ocr_required_page_never_silently_becomes_high_confidence():
    page = PDFPageData(
        1, 500, 700, "치아보철치료비 권장 200만원 가입 50만원 부족 150만원",
        page_type=PageType.COVERAGE_ANALYSIS, text_quality="TEXT_GARBLED", ocr_required=True,
    )
    document = PDFDocumentData(__file__, "synthetic.pdf", 1, {}, False, [page])
    result = GenericParser().parse(document)
    assert result.aggregate_coverages[0].confidence == "LOW"
    issue = next(issue for issue in result.validation_issues if issue.code == "OCR_REQUIRED")
    assert issue.severity is ValidationSeverity.WARNING
