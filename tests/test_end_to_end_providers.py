from pathlib import Path

import pytest

from dental_coverage_analyzer.core.pdf import OCRResult, OCRStatus, analyze_pdf


class SequentialOCR:
    def __init__(self, texts: list[str], status: OCRStatus = OCRStatus.SUCCESS) -> None:
        self.texts = iter(texts)
        self.status = status

    def recognize(self, _image: bytes, languages=("kor", "eng")) -> OCRResult:
        del languages
        text = next(self.texts, "")
        return OCRResult(self.status, text=text if self.status is OCRStatus.SUCCESS else None, confidence=92.0)


def blank_pdf(tmp_path: Path, pages: int, numeric_text: str | None = None) -> Path:
    fitz = pytest.importorskip("fitz", reason="PyMuPDF가 필요한 provider E2E 테스트")
    path = tmp_path / "provider-synthetic.pdf"
    document = fitz.open()
    for index in range(pages):
        page = document.new_page()
        if numeric_text and index == 0:
            page.insert_text((40, 50), numeric_text)
    document.save(path)
    document.close()
    return path


def test_meritz_e2e_ocr_and_aggregate_dedup(tmp_path: Path):
    path = blank_pdf(tmp_path, 2)
    common = (
        "메리츠화재 간편보장분석 보험 가입 보장 담보 상세 내용 "
        "치아보철치료비 권장 200만원 가입 50만원 부족 150만원 상태 부족"
    )
    second = common + "\n치아보존치료비 권장 50만원 가입 0원 부족 50만원 상태 미가입"
    result = analyze_pdf(path, ocr_engine=SequentialOCR([common, second]))
    assert result.provider == "MERITZ"
    assert len(result.aggregate_coverages) == 2
    prosthetic = next(item for item in result.aggregate_coverages if "보철" in item.raw_name)
    assert prosthetic.enrolled_amount == 500_000
    assert prosthetic.source_pages == [1, 2]
    assert result.support_summary.ocr_success_pages == 2


def test_samsung_e2e_keeps_levels_and_inherits_verified_continuation(tmp_path: Path):
    path = blank_pdf(tmp_path, 3)
    aggregate = (
        "삼성화재 보장별 분석 보험 가입 보장 담보 권장 가입금액 현재 가입금액 "
        "치아보철 치료비 권장 200만원 현재 가입 0원 상태 미가입\n"
        "치아보존 치료비 권장 20만원 현재 가입 37만원 상태 충분"
    )
    detail = (
        "삼성화재 상품별 상세 현황 보험 가입 보장 담보\n"
        "보험회사: 라이나(에이스)손해보험\n"
        "상품명: (무)더핏 THE든든한 치아보험 1종(갱신형)\n"
        "컴퍼짓레진 / 치과치료(보존치료) / 9만원"
    )
    continuation = (
        "세부 치과 보장 담보 가입금액 치료 내역 안내\n"
        "스케일링 / 기타치과담보 / 1만원\n근관치료 / 기타치과담보 / 2만원"
    )
    result = analyze_pdf(path, ocr_engine=SequentialOCR([aggregate, detail, continuation]))
    assert result.provider == "SAMSUNG"
    assert len(result.contracts) == 1
    assert len(result.aggregate_coverages) == 2
    assert {rider.raw_name for rider in result.dental_riders} >= {"컴퍼짓레진", "스케일링", "근관치료"}
    assert all(rider.product_name for rider in result.dental_riders)
    assert result.aggregate_coverages[1].enrolled_amount == 370_000
    assert next(r for r in result.dental_riders if r.raw_name == "컴퍼짓레진").enrolled_amount == 90_000


def test_lotte_like_garbled_page_without_ocr_does_not_crash(tmp_path: Path):
    numeric = "167,400 238,500 5,000 30 10,142 200000 300000 400000 500000"
    path = blank_pdf(tmp_path, 1, numeric)
    result = analyze_pdf(path, ocr_engine=SequentialOCR([], OCRStatus.NOT_CONFIGURED))
    page = result.document.pages[0]
    assert page.ocr_required is True
    assert page.ocr_status == "NOT_CONFIGURED"
    assert any(issue.code == "OCR_NOT_AVAILABLE" for issue in result.validation_issues)
    assert result.support_summary.ocr_failed_pages == 1

