from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class OCRStatus(StrEnum):
    SUCCESS = "SUCCESS"
    NOT_CONFIGURED = "NOT_CONFIGURED"
    FAILED = "FAILED"


@dataclass(frozen=True, slots=True)
class OCRWord:
    text: str
    bbox: tuple[float, float, float, float]
    confidence: float
    block_no: int = 0
    line_no: int = 0
    word_no: int = 0


@dataclass(frozen=True, slots=True)
class OCRResult:
    status: OCRStatus
    text: str | None = None
    confidence: float | None = None
    reason: str | None = None
    words: tuple[OCRWord, ...] = ()


class OCREngine(Protocol):
    """로컬 page image bytes만 받는 OCR adapter 계약."""

    def recognize(self, image: bytes, languages: tuple[str, ...] = ("kor", "eng")) -> OCRResult: ...


class NotConfiguredOCREngine:
    """외부 전송 없이 OCR 미설정 상태를 안전하게 명시한다."""

    def recognize(self, image: bytes, languages: tuple[str, ...] = ("kor", "eng")) -> OCRResult:
        del image, languages
        return OCRResult(OCRStatus.NOT_CONFIGURED, reason="로컬 OCR 엔진이 설정되지 않았습니다")
