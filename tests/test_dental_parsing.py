from pathlib import Path

from dental_coverage_analyzer.core.dental import DentalProductDetector
from dental_coverage_analyzer.core.parsers.generic_parser import GenericParser
from dental_coverage_analyzer.models import CauseType, PDFDocumentData, PDFPageData, PageType, PaymentUnit

FIXTURES = Path(__file__).parent / "fixtures"


def parse_product_text(text: str):
    page = PDFPageData(
        3, 500, 700, text, page_type=PageType.PRODUCT_DETAIL,
        text_quality="TEXT_OK", ocr_required=False,
    )
    document = PDFDocumentData(__file__, "synthetic.pdf", 1, {}, False, [page])
    return GenericParser().parse(document)


def test_dental_product_and_riders_are_linked_to_contract():
    text = (FIXTURES / "samsung_contract_riders.txt").read_text(encoding="utf-8")
    result = parse_product_text(text)
    assert len(result.contracts) == 1
    assert DentalProductDetector().detect(result.contracts[0].product_name).is_candidate
    composite = next(rider for rider in result.dental_riders if rider.raw_name == "컴퍼짓레진")
    assert composite.insurer == "라이나(에이스)손해보험"
    assert "THE든든한 치아보험" in composite.product_name
    assert composite.category == "보존치료"
    assert composite.enrolled_amount == 90_000
    assert composite.raw_amount == "9만원"


def test_cause_and_payment_units_remain_distinct():
    text = (FIXTURES / "samsung_contract_riders.txt").read_text(encoding="utf-8")
    riders = parse_product_text(text).dental_riders
    simple = [rider for rider in riders if "단순 발치" in rider.raw_name]
    assert len(simple) == 2
    assert {rider.cause_type for rider in simple} == {CauseType.DISEASE, CauseType.ACCIDENT}
    impacted = next(rider for rider in riders if "완전히 매복" in rider.raw_name)
    panorama = next(rider for rider in riders if "파노라마" in rider.raw_name)
    assert impacted.payment_unit is PaymentUnit.PER_TOOTH
    assert impacted.category == "발치"
    assert panorama.payment_unit is PaymentUnit.PER_OCCURRENCE


def test_original_name_has_priority_over_generic_credit_name():
    text = """보험회사: 라이나(에이스)손해보험
상품명: (무)합성 치아보험
치주질환수술보험금 / 기타수술 / 5만원"""
    rider = parse_product_text(text).dental_riders[0]
    assert rider.raw_name == "치주질환수술보험금"
    assert rider.credit_information_name == "기타수술"
    assert rider.category == "치주치료"


def test_false_positive_rows_are_excluded():
    text = """상품별 상세 현황
치매진단비 1,000만원
골절진단비 20만원
화상진단비 20만원
질병수술비 30만원
자동차사고부상치료비 50만원"""
    assert parse_product_text(text).dental_riders == []


def test_aggregate_and_rider_are_both_preserved():
    aggregate_page = PDFPageData(
        1, 500, 700, "치아보존치료비 권장 20만원 가입 37만원 충분",
        page_type=PageType.COVERAGE_ANALYSIS, text_quality="TEXT_OK", ocr_required=False,
    )
    product_page = PDFPageData(
        2, 500, 700,
        "보험회사: 라이나(에이스)손해보험\n상품명: (무)합성 치아보험\n컴퍼짓레진 9만원",
        page_type=PageType.PRODUCT_DETAIL, text_quality="TEXT_OK", ocr_required=False,
    )
    document = PDFDocumentData(__file__, "synthetic.pdf", 2, {}, False, [aggregate_page, product_page])
    result = GenericParser().parse(document)
    assert len(result.aggregate_coverages) == 1
    assert len(result.dental_riders) == 1
    assert result.aggregate_coverages[0].enrolled_amount == 370_000
    assert result.dental_riders[0].enrolled_amount == 90_000
