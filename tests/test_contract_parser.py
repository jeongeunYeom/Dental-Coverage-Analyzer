from datetime import date
from pathlib import Path

from dental_coverage_analyzer.core.parsers.contract_parser import InsuranceContractParser
from dental_coverage_analyzer.models import PDFDocumentData, PDFPageData, PDFWord, PageType

FIXTURES = Path(__file__).parent / "fixtures"


def test_samsung_style_contract_is_parsed_without_inventing_fields():
    text = (FIXTURES / "samsung_contract_riders.txt").read_text(encoding="utf-8")
    page = PDFPageData(
        4, 500, 700, text, page_type=PageType.PRODUCT_DETAIL,
        text_quality="TEXT_OK", ocr_required=False,
    )
    document = PDFDocumentData(__file__, "synthetic.pdf", 1, {}, False, [page])
    contracts = InsuranceContractParser().parse(document).items
    assert len(contracts) == 1
    contract = contracts[0]
    assert contract.insurer == "라이나(에이스)손해보험"
    assert contract.product_name == "(무)더핏 THE든든한 치아보험 1종(갱신형)"
    assert contract.enrollment_date == date(2025, 12, 23)
    assert contract.coverage_period == "2025-12-23 ~ 2063-12-23"
    assert contract.payment_cycle == "월납"
    assert contract.payment_period == "38년납"
    assert contract.maturity == "80세만기"
    assert contract.monthly_premium == 17_610
    assert contract.policyholder is None


def test_multiple_explicit_contract_sections_are_not_collapsed():
    text = """보험회사: 합성손해보험
상품명: (무)첫번째 치아보험
보험회사: 예시생명
상품명: (무)두번째 치아보험"""
    page = PDFPageData(
        1, 500, 700, text, page_type=PageType.PRODUCT_DETAIL,
        text_quality="TEXT_OK", ocr_required=False,
    )
    document = PDFDocumentData(__file__, "synthetic.pdf", 1, {}, False, [page])
    contracts = InsuranceContractParser().parse(document).items
    assert [(item.insurer, item.product_name) for item in contracts] == [
        ("합성손해보험", "(무)첫번째 치아보험"),
        ("예시생명", "(무)두번째 치아보험"),
    ]


def test_table_headers_are_not_invented_as_contract_values():
    text = "보험회사 담보 이름 신용정보원 담보 이름 가입금액"
    page = PDFPageData(
        1, 500, 700, text, page_type=PageType.PRODUCT_DETAIL,
        text_quality="TEXT_OK", ocr_required=False,
    )
    document = PDFDocumentData(__file__, "synthetic.pdf", 1, {}, False, [page])
    assert InsuranceContractParser().parse(document).items == []


def test_bbox_contract_matrix_maps_headers_to_cells():
    words = [
        PDFWord("보험회사", 10, 20, 70, 30, 0, 0, 0),
        PDFWord("상품명", 150, 20, 200, 30, 0, 0, 1),
        PDFWord("보험기간", 330, 20, 390, 30, 0, 0, 2),
        PDFWord("월보험료", 450, 20, 510, 30, 0, 0, 3),
        PDFWord("합성손해보험", 10, 50, 80, 60, 1, 0, 0),
        PDFWord("합성치아보험", 150, 50, 230, 60, 1, 0, 1),
        PDFWord("2025~2060", 330, 50, 410, 60, 1, 0, 2),
        PDFWord("17,610원", 450, 50, 510, 60, 1, 0, 3),
    ]
    page = PDFPageData(
        1, 600, 700, "보험회사 상품명 보험기간 월보험료",
        words=words, effective_words=words, page_type=PageType.PRODUCT_MATRIX,
        text_quality="TEXT_OK", ocr_required=False,
    )
    document = PDFDocumentData(__file__, "synthetic.pdf", 1, {}, False, [page])
    contract = InsuranceContractParser().parse(document).items[0]
    assert contract.insurer == "합성손해보험"
    assert contract.product_name == "합성치아보험"
    assert contract.coverage_period == "2025~2060"
    assert contract.monthly_premium == 17_610
    assert contract.sources[0].bbox == (10, 50, 510, 60)


def test_vertical_product_matrix_extracts_multiple_contract_columns_only_with_equal_cells():
    words = [
        PDFWord("보험회사", 10, 20, 70, 30, 0, 0, 0),
        PDFWord("합성손해보험", 150, 20, 240, 30, 0, 0, 1),
        PDFWord("예시생명보험", 350, 20, 440, 30, 0, 0, 2),
        PDFWord("상품명", 10, 50, 70, 60, 1, 0, 0),
        PDFWord("첫째치아보험", 150, 50, 240, 60, 1, 0, 1),
        PDFWord("둘째치아보험", 350, 50, 440, 60, 1, 0, 2),
        PDFWord("월보험료", 10, 80, 70, 90, 2, 0, 0),
        PDFWord("10,000원", 150, 80, 240, 90, 2, 0, 1),
        PDFWord("20,000원", 350, 80, 440, 90, 2, 0, 2),
    ]
    page = PDFPageData(
        1, 600, 700, "보험회사 상품명 월보험료", words=words, effective_words=words,
        page_type=PageType.PRODUCT_MATRIX, text_quality="TEXT_OK", ocr_required=False,
    )
    document = PDFDocumentData(__file__, "synthetic.pdf", 1, {}, False, [page])
    contracts = InsuranceContractParser().parse(document).items
    assert [(item.insurer, item.monthly_premium) for item in contracts] == [
        ("합성손해보험", 10_000), ("예시생명보험", 20_000),
    ]


def test_same_product_on_different_pages_is_not_merged_without_identity_fields():
    pages = [
        PDFPageData(
            number, 500, 700, "보험회사: 합성손해보험\n상품명: 동일 치아보험",
            page_type=PageType.PRODUCT_DETAIL, text_quality="TEXT_OK", ocr_required=False,
        )
        for number in (1, 2)
    ]
    document = PDFDocumentData(__file__, "synthetic.pdf", 2, {}, False, pages)
    result = InsuranceContractParser().parse(document)
    assert len(result.items) == 2
    assert any(issue.code == "CONTRACT_IDENTITY_CONFLICT" for issue in result.issues)
