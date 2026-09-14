from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from dental_coverage_analyzer.core.resources import load_config
from dental_coverage_analyzer.models import Confidence


@dataclass(frozen=True, slots=True)
class DentalProductDetection:
    is_candidate: bool
    confidence: Confidence
    matched_keywords: tuple[str, ...]
    reason: str


class DentalProductDetector:
    def __init__(self, keywords_file: str | Path | None = None) -> None:
        if keywords_file:
            with Path(keywords_file).open(encoding="utf-8") as stream:
                config = json.load(stream)
        else:
            config = load_config("dental_keywords.json")
        self.keywords = tuple(config["product"])

    def detect(self, product_name: str | None) -> DentalProductDetection:
        if not product_name:
            return DentalProductDetection(False, Confidence.LOW, (), "상품명이 확인되지 않음")
        matched = tuple(
            keyword for keyword in self.keywords
            if keyword.casefold() in product_name.casefold()
        )
        if matched:
            return DentalProductDetection(
                True, Confidence.HIGH, matched,
                f"상품명에서 치아보험 키워드 확인: {', '.join(matched)}",
            )
        return DentalProductDetection(False, Confidence.LOW, (), "치아보험 상품 키워드 없음")
