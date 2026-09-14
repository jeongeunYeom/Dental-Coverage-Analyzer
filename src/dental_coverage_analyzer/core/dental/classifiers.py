from __future__ import annotations

import json
from pathlib import Path

from dental_coverage_analyzer.core.resources import load_config
from dental_coverage_analyzer.models import CauseType, PaymentUnit


class DentalCategoryClassifier:
    def __init__(self, categories_file: str | Path | None = None) -> None:
        if categories_file:
            with Path(categories_file).open(encoding="utf-8") as stream:
                self.categories = json.load(stream)
        else:
            self.categories = load_config("dental_categories.json")

    def classify(self, raw_name: str) -> str:
        compact = "".join(raw_name.casefold().split())
        matches: list[tuple[int, str]] = []
        for category, keywords in self.categories.items():
            for keyword in keywords:
                if "".join(keyword.casefold().split()) in compact:
                    matches.append((len(keyword), category))
        return max(matches)[1] if matches else "기타 치과"


def extract_cause_type(text: str) -> CauseType:
    disease = "질병" in text
    accident = "상해" in text
    if disease and accident:
        return CauseType.BOTH
    if disease:
        return CauseType.DISEASE
    if accident:
        return CauseType.ACCIDENT
    return CauseType.UNKNOWN


def extract_payment_unit(text: str) -> PaymentUnit:
    compact = "".join(text.split())
    if "치아당" in compact:
        return PaymentUnit.PER_TOOTH
    if "촬영당" in compact or "회당" in compact:
        return PaymentUnit.PER_OCCURRENCE
    if "치료당" in compact:
        return PaymentUnit.PER_TREATMENT
    if "연간1회" in compact or "연1회" in compact:
        return PaymentUnit.PER_YEAR
    return PaymentUnit.UNKNOWN
