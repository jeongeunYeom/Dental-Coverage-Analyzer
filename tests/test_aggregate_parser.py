from dental_coverage_analyzer.core.parsers.aggregate_parser import AggregateCoverageParser
from dental_coverage_analyzer.models import PDFDocumentData, PDFPageData, PDFWord, PageType


def document_with_pages(*texts: str) -> PDFDocumentData:
    pages = [
        PDFPageData(
            number, 500, 700, text, page_type=PageType.COVERAGE_ANALYSIS,
            text_quality="TEXT_OK", ocr_required=False,
        )
        for number, text in enumerate(texts, 1)
    ]
    return PDFDocumentData(__file__, "synthetic.pdf", len(pages), {}, False, pages)


def test_meritz_aggregate_amount_semantics_and_ratio():
    text = """보장별 분석
치아보철치료비 권장 200만원 가입 50만원 부족 150만원 상태 부족
치아보존치료비 권장 50만원 가입 0원 부족 50만원 상태 미가입"""
    result = AggregateCoverageParser().parse(document_with_pages(text))
    assert len(result.items) == 2
    prosthetic, restorative = result.items
    assert (prosthetic.recommended_amount, prosthetic.enrolled_amount) == (2_000_000, 500_000)
    assert prosthetic.shortage_amount == 1_500_000
    assert prosthetic.normalized_shortage == 1_500_000
    assert prosthetic.calculated_ratio == 25.0
    assert prosthetic.status == "부족"
    assert prosthetic.normalized_status == "INSUFFICIENT"
    assert restorative.enrolled_amount == 0
    assert restorative.normalized_status == "NOT_ENROLLED"


def test_samsung_surplus_is_calculated_without_overwriting_raw_difference():
    text = "치아보존 치료비 권장 20만원 현재 가입 37만원 과부족 +17만원 상태 충분"
    item = AggregateCoverageParser().parse(document_with_pages(text)).items[0]
    assert item.calculated_ratio == 185.0
    assert item.raw_difference == "+17만원"
    assert item.normalized_shortage == 0
    assert item.normalized_surplus == 170_000


def test_samsung_positional_zero_requires_and_uses_headers():
    text = "담보명 권장 가입 과부족\n치아보철 치료비 200만 0 -200만"
    item = AggregateCoverageParser().parse(document_with_pages(text)).items[0]
    assert item.recommended_amount == 2_000_000
    assert item.enrolled_amount == 0
    assert item.raw_difference == "-200만"
    assert item.normalized_status == "NOT_ENROLLED"


def test_short_samsung_aggregate_name_is_supported():
    text = "치아보철 권장 200만원 가입 0원 상태 미가입"
    item = AggregateCoverageParser().parse(document_with_pages(text)).items[0]
    assert item.normalized_name == "치아보철"
    assert item.enrolled_amount == 0


def test_table_unit_is_inherited_only_when_explicit():
    with_unit = "단위: 만원\n담보명 권장 가입 부족\n치아보철치료비 200 50 150 부족"
    item = AggregateCoverageParser().parse(document_with_pages(with_unit)).items[0]
    assert item.recommended_amount == 2_000_000
    assert item.enrolled_amount == 500_000
    without_unit = "담보명 권장 가입 부족\n치아보철치료비 200 50 150 부족"
    assert AggregateCoverageParser().parse(document_with_pages(without_unit)).items == []


def test_bbox_header_columns_map_amount_meanings():
    page = PDFPageData(
        1, 500, 700, "권장금액 가입금액 부족금액\n치아보철치료비 200만원 50만원 150만원",
        words=[
            PDFWord("권장금액", 200, 20, 250, 30, 0, 0, 0),
            PDFWord("가입금액", 300, 20, 350, 30, 0, 0, 1),
            PDFWord("부족금액", 400, 20, 450, 30, 0, 0, 2),
            PDFWord("치아보철치료비", 20, 50, 150, 60, 1, 0, 0),
            PDFWord("200만원", 200, 50, 250, 60, 1, 0, 1),
            PDFWord("50만원", 300, 50, 350, 60, 1, 0, 2),
            PDFWord("150만원", 400, 50, 450, 60, 1, 0, 3),
        ],
        page_type=PageType.COVERAGE_ANALYSIS, text_quality="TEXT_OK", ocr_required=False,
    )
    document = PDFDocumentData(__file__, "synthetic.pdf", 1, {}, False, [page])
    item = AggregateCoverageParser().parse(document).items[0]
    assert item.recommended_amount == 2_000_000
    assert item.enrolled_amount == 500_000
    assert item.raw_difference == "150만원"
    assert "bbox" in item.confidence_reason
    assert item.representative_source.bbox == (20, 50, 450, 60)


def test_duplicate_aggregate_merges_pages_without_summing():
    row = "치아보철치료비 권장 200만원 가입 50만원 부족 150만원 상태 부족"
    result = AggregateCoverageParser().parse(document_with_pages(row, row, row))
    assert len(result.items) == 1
    assert result.items[0].enrolled_amount == 500_000
    assert result.items[0].source_pages == [1, 2, 3]


def test_conflicting_aggregate_values_are_kept_and_reported():
    first = "치아보철치료비 권장 200만원 가입 50만원 부족 150만원"
    second = "치아보철치료비 권장 200만원 가입 70만원 부족 130만원"
    result = AggregateCoverageParser().parse(document_with_pages(first, second))
    assert len(result.items) == 2
    assert any(issue.code == "AGGREGATE_AMOUNT_CONFLICT" for issue in result.issues)


def test_difference_mismatch_creates_issue_instead_of_changing_source():
    text = "치아보철치료비 권장 200만원 가입 50만원 부족 120만원"
    result = AggregateCoverageParser().parse(document_with_pages(text))
    assert result.items[0].raw_difference == "120만원"
    assert result.items[0].normalized_shortage == 1_500_000
    assert any(issue.code == "DIFFERENCE_MISMATCH" for issue in result.issues)
