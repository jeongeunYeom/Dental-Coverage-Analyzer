from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from dental_coverage_analyzer.core.resources import config_path
from dental_coverage_analyzer.models import Confidence, PageType


@dataclass(frozen=True, slots=True)
class PageClassification:
    page_type: PageType
    scores: dict[str, float]
    confidence: Confidence
    reason: str


class PageClassifier:
    def __init__(self, patterns_file: str | Path | None = None) -> None:
        path = Path(patterns_file) if patterns_file else config_path("page_patterns.json")
        with path.open(encoding="utf-8") as stream:
            self.patterns: dict[str, dict[str, object]] = json.load(stream)

    def classify(self, text: str) -> PageClassification:
        normalized = " ".join((text or "").casefold().split())
        scores: dict[str, float] = {}
        matched: dict[str, list[str]] = {}
        for name, rule in self.patterns.items():
            score = 0.0
            terms: list[str] = []
            for keyword, weight in dict(rule.get("positive_keywords", {})).items():
                if keyword.casefold() in normalized:
                    score += float(weight)
                    terms.append(keyword)
            for keyword, weight in dict(rule.get("negative_keywords", {})).items():
                if keyword.casefold() in normalized:
                    score -= float(weight)
            scores[name] = score
            matched[name] = terms

        eligible = [
            name for name, score in scores.items()
            if score >= float(self.patterns[name].get("minimum_score", 1))
        ]
        if not eligible:
            return PageClassification(
                PageType.UNKNOWN, scores, Confidence.LOW,
                "설정된 페이지 유형의 최소 점수를 충족하지 못함",
            )
        winner = max(eligible, key=lambda name: scores[name])
        runner_up = max((scores[name] for name in eligible if name != winner), default=0.0)
        margin = scores[winner] - runner_up
        confidence = Confidence.HIGH if len(matched[winner]) >= 2 and margin >= 2 else Confidence.MEDIUM
        return PageClassification(
            PageType(winner), scores, confidence,
            f"일치 키워드: {', '.join(matched[winner])}; 점수 {scores[winner]:g}",
        )

