from datetime import date
from pathlib import Path

from dental_coverage_analyzer.core.parsers.contract_parser import InsuranceContractParser
from dental_coverage_analyzer.models import PDFDocumentData, PDFPageData, PageType

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
