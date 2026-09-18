from __future__ import annotations


def confidence_label(value: object) -> str:
    raw = getattr(value, "value", value)
    return {"HIGH": "높음", "MEDIUM": "보통", "LOW": "확인 필요"}.get(str(raw), "확인 필요")


def issue_label(code: str) -> str:
    return {
        "AGGREGATE_CANONICAL_CONFLICT": "보장정보 확인 필요",
        "AGGREGATE_AMOUNT_CONFLICT": "보장금액 확인 필요",
        "OCR_NOT_AVAILABLE": "스캔 문서 확인 필요",
        "OCR_FAILED": "스캔 문서 확인 필요",
        "LOW_OCR_CONFIDENCE": "문서 내용 확인 필요",
        "CONTRACT_LINK_UNCERTAIN": "보험상품 연결 확인 필요",
    }.get(code, "분석 결과 확인 필요")
