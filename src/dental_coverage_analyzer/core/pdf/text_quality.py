from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import re


class TextQualityStatus(StrEnum):
    TEXT_OK = "TEXT_OK"
    TEXT_PARTIAL = "TEXT_PARTIAL"
    TEXT_GARBLED = "TEXT_GARBLED"
    IMAGE_ONLY = "IMAGE_ONLY"


INSURANCE_TERMS = ("보험", "가입", "보장", "담보", "치아", "치과", "계약", "보험료")
_MEANINGFUL_WORD = re.compile(r"[가-힣A-Za-z]{2,}")
_HANGUL = re.compile(r"[가-힣]")
_DIGIT = re.compile(r"\d")
_BROKEN = re.compile(r"[\uFFFD]|[\x00-\x08\x0b\x0c\x0e-\x1f]")
# OCR/PDF extraction often inserts spaces between nearly every Korean glyph.
_ODD_SPACING = re.compile(r"(?:[가-힣A-Za-z0-9]\s+){4,}[가-힣A-Za-z0-9]")


@dataclass(frozen=True, slots=True)
class TextQualityResult:
    status: TextQualityStatus
    total_characters: int
    hangul_ratio: float
    digit_ratio: float
    meaningful_word_count: int
    insurance_term_count: int
    insurance_term_rate: float
    broken_character_ratio: float
    odd_spacing_ratio: float
    ocr_required: bool
    reasons: tuple[str, ...]


def analyze_text_quality(text: str | None) -> TextQualityResult:
    raw = text or ""
    compact = "".join(raw.split())
    total = len(compact)
    if total < 5:
        return TextQualityResult(
            TextQualityStatus.IMAGE_ONLY, total, 0.0, 0.0, 0, 0, 0.0,
            0.0, 0.0, True, ("유효한 Text Layer 문자가 거의 없음",),
        )

    hangul = len(_HANGUL.findall(compact))
    digits = len(_DIGIT.findall(compact))
    broken = len(_BROKEN.findall(raw))
    words = _MEANINGFUL_WORD.findall(raw)
    detected_terms = sum(term in compact for term in INSURANCE_TERMS)
    odd_chars = sum(len(match.group(0)) for match in _ODD_SPACING.finditer(raw))
    hangul_ratio = hangul / total
    digit_ratio = digits / total
    broken_ratio = broken / max(len(raw), 1)
    odd_ratio = min(odd_chars / max(len(raw), 1), 1.0)
    term_rate = detected_terms / len(INSURANCE_TERMS)
    reasons: list[str] = []

    severely_numeric = total >= 30 and digit_ratio >= 0.55 and hangul_ratio < 0.08
    semantically_empty = total >= 30 and hangul_ratio < 0.05 and detected_terms == 0
    structurally_broken = broken_ratio >= 0.05 or odd_ratio >= 0.65
    if severely_numeric:
        reasons.append("숫자 비율이 높지만 한글 비율이 지나치게 낮음")
    if semantically_empty:
        reasons.append("보험 관련 의미 단어를 찾지 못함")
    if structurally_broken:
        reasons.append("깨진 문자 또는 비정상 공백 패턴이 많음")

    if severely_numeric or semantically_empty or structurally_broken:
        status = TextQualityStatus.TEXT_GARBLED
    elif total >= 40 and hangul_ratio >= 0.20 and (detected_terms >= 2 or len(words) >= 8):
        status = TextQualityStatus.TEXT_OK
        reasons.append("충분한 한글 문맥과 의미 단어가 확인됨")
    else:
        status = TextQualityStatus.TEXT_PARTIAL
        reasons.append("일부 텍스트는 있으나 정상 판정 기준에 미달함")

    return TextQualityResult(
        status=status,
        total_characters=total,
        hangul_ratio=hangul_ratio,
        digit_ratio=digit_ratio,
        meaningful_word_count=len(words),
        insurance_term_count=detected_terms,
        insurance_term_rate=term_rate,
        broken_character_ratio=broken_ratio,
        odd_spacing_ratio=odd_ratio,
        ocr_required=status is not TextQualityStatus.TEXT_OK,
        reasons=tuple(reasons),
    )
