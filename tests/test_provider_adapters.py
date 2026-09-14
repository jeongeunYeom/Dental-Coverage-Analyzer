from dental_coverage_analyzer.core.parsers.adapters import LotteAdapter, MeritzAdapter, SamsungAdapter
from dental_coverage_analyzer.core.parsers.provider_detector import ProviderDetector, ProviderType
from dental_coverage_analyzer.models import PDFDocumentData, PDFPageData, PageType


def document(*texts: str) -> PDFDocumentData:
    pages = [PDFPageData(i, 500, 700, text, ocr_required=False) for i, text in enumerate(texts, 1)]
    return PDFDocumentData(__file__, "irrelevant-name.pdf", len(pages), {}, False, pages)


def test_provider_detection_uses_content_scores_not_filename():
    cases = [
        ("메리츠화재 간편보장분석 담보별 진단현황", ProviderType.MERITZ),
        ("삼성화재 상품별 상세 현황 신용정보원 담보 이름", ProviderType.SAMSUNG),
        ("롯데손해보험 한장 보장 현황 세부 가입 현황", ProviderType.LOTTE),
    ]
    for text, expected in cases:
        result = ProviderDetector().detect(document(text))
        assert result.provider is expected
        assert result.confidence == "HIGH"


def test_meritz_adapter_only_adds_page_type_hint():
    data = document("메리츠화재 담보별 진단 현황 치아보철치료비")
    MeritzAdapter().apply_hints(data)
    assert data.pages[0].page_type is PageType.DIAGNOSIS_DETAIL
    assert data.pages[0].parser_hints["provider_page_type"].startswith("MERITZ")


def test_samsung_continuation_requires_consecutive_page_without_new_header():
    data = document(
        "삼성화재 상품별 상세 현황 보험회사 라이나생명 상품명 합성 치아보험",
        "컴퍼짓레진 9만원 스케일링 1만원",
        "보험회사 새보험사 상품명 새상품 컴퍼짓레진 9만원",
    )
    SamsungAdapter().apply_hints(data)
    assert data.pages[1].page_type is PageType.PRODUCT_DETAIL
    assert data.pages[1].parser_hints["inherit_product_context"] is True
    assert "inherit_product_context" not in data.pages[2].parser_hints


def test_lotte_adapter_requests_ocr_without_reconstructing_data():
    data = document("167,400 238,500 5,000 30 10,142")
    data.pages[0].text_quality = "TEXT_GARBLED"
    LotteAdapter().apply_hints(data)
    assert data.pages[0].parser_hints == {"lotte_ocr_required": True}
    assert data.pages[0].text == "167,400 238,500 5,000 30 10,142"

