import pytest

from dental_coverage_analyzer.core.pdf.page_classifier import PageClassifier
from dental_coverage_analyzer.models import PageType


@pytest.mark.parametrize(("text", "expected"), [
    (
        "가명고객님의 보장별 분석\n분류 보장 상세 진단 권장 가입금액 현재 가입금액",
        PageType.COVERAGE_ANALYSIS,
    ),
    (
        "가명고객님의 상품별 상세 현황\n보험회사 담보 이름 신용정보원 담보 이름 가입금액",
        PageType.PRODUCT_DETAIL,
    ),
    ("안내 및 유의사항", PageType.NOTICE),
    ("한장 보장 현황 보험별 보장 현황", PageType.ONE_PAGE_SUMMARY),
])
def test_score_based_page_classification(text, expected):
    result = PageClassifier().classify(text)
    assert result.page_type is expected
    assert result.scores[expected.value] > 0


def test_unknown_when_no_pattern_reaches_threshold():
    assert PageClassifier().classify("임의의 짧은 페이지").page_type is PageType.UNKNOWN

