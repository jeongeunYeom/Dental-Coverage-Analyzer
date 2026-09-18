from pathlib import Path

from dental_coverage_analyzer.core.pdf.page_signals import PageSignalDetector
from dental_coverage_analyzer.models import Confidence

FIXTURES = Path(__file__).parent / "fixtures"


def test_dental_coverage_terms_increase_candidate_score():
    detector = PageSignalDetector()
    keywords, score = detector.dental_signals("치아보철치료비 치아보존치료비 가입금액")
    assert {"치아", "보철", "보존"}.issubset(keywords)
    assert score > 0


def test_dementia_only_is_not_a_dental_candidate():
    keywords, score = PageSignalDetector().dental_signals("치매진단비 1,000만원")
    assert keywords == []
    assert score == 0.0


def test_insurer_and_product_candidates_keep_evidence():
    text = (FIXTURES / "product_layout.txt").read_text(encoding="utf-8")
    detector = PageSignalDetector()
    insurers = detector.insurer_candidates(text, [], 3)
    products = detector.product_candidates(text, [], 3)
    assert insurers[0].value == "라이나(에이스)손해보험"
    assert insurers[0].page_number == 3
    assert insurers[0].confidence is Confidence.HIGH
    assert any("THE든든한 치아보험" in item.value for item in products)


def test_unknown_insurer_suffix_requires_header_context():
    detector = PageSignalDetector()
    candidates = detector.insurer_candidates("보험회사\n새싹손해보험", [], 1)
    assert candidates[0].value == "새싹손해보험"
    assert candidates[0].confidence is Confidence.MEDIUM
