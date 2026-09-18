from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from dental_coverage_analyzer.core.resources import load_config
from dental_coverage_analyzer.models import Confidence, PDFDocumentData


class ProviderType(StrEnum):
    GENERIC = "GENERIC"
    MERITZ = "MERITZ"
    SAMSUNG = "SAMSUNG"
    LOTTE = "LOTTE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class ProviderDetection:
    provider: ProviderType
    confidence: Confidence
    scores: dict[str, float]
    reason: str


class ProviderDetector:
    def __init__(self) -> None:
        self.patterns = load_config("provider_patterns.json")

    def detect(self, document: PDFDocumentData) -> ProviderDetection:
        text = "\n".join(page.effective_text or page.text for page in document.pages).casefold()
        scores: dict[str, float] = {}
        matches: dict[str, list[str]] = {}
        for provider, rule in self.patterns.items():
            found = [keyword for keyword in rule["positive_keywords"] if keyword.casefold() in text]
            scores[provider] = sum(float(rule["positive_keywords"][keyword]) for keyword in found)
            matches[provider] = found
        eligible = [
            name for name, score in scores.items()
            if score >= float(self.patterns[name]["minimum_score"])
        ]
        if not eligible:
            return ProviderDetection(ProviderType.UNKNOWN, Confidence.LOW, scores, "provider 식별 근거 부족")
        winner = max(eligible, key=lambda name: scores[name])
        confidence = Confidence.HIGH if winner != "GENERIC" and scores[winner] >= 6 else Confidence.MEDIUM
        return ProviderDetection(
            ProviderType(winner), confidence, scores,
            f"PDF 내부 일치 신호: {', '.join(matches[winner])}",
        )

