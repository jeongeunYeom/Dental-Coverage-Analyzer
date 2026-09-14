from __future__ import annotations

import json
from pathlib import Path
import re

from dental_coverage_analyzer.core.resources import config_path
from dental_coverage_analyzer.models import Confidence, ExtractionCandidate, PDFWord


def _load_json(path: str | Path) -> dict:
    with Path(path).open(encoding="utf-8") as stream:
        return json.load(stream)


def _bbox_for_text(words: list[PDFWord], value: str) -> tuple[float, float, float, float] | None:
    compact_value = "".join(value.split()).casefold()
    matches = [word for word in words if "".join(word.text.split()).casefold() in compact_value]
    if not matches:
        return None
    return min(w.x0 for w in matches), min(w.y0 for w in matches), max(w.x1 for w in matches), max(w.y1 for w in matches)


class PageSignalDetector:
    def __init__(
        self,
        dental_file: str | Path | None = None,
        insurer_file: str | Path | None = None,
    ) -> None:
        dental = _load_json(dental_file or config_path("dental_keywords.json"))
        insurer = _load_json(insurer_file or config_path("insurer_patterns.json"))
        self.dental_keywords: list[str] = dental["include"]
        self.dental_exclusions: list[str] = dental["exclude"]
        self.product_keywords: list[str] = dental["product"]
        # 긴 이름부터 검사해 '라이나'가 긴 정식 명칭을 가리지 않게 한다.
        self.insurers: list[str] = sorted(insurer["insurers"], key=len, reverse=True)
        self.insurer_headers: list[str] = insurer["context_headers"]

    def dental_signals(self, text: str) -> tuple[list[str], float]:
        searchable = text or ""
        for exclusion in self.dental_exclusions:
            searchable = searchable.replace(exclusion, " ")
        found = sorted({keyword for keyword in self.dental_keywords if keyword.casefold() in searchable.casefold()})
        # 중첩 키워드가 많아도 과도하게 확정하지 않는 0..1 후보 점수이다.
        weighted = sum(2 if len(keyword) >= 4 else 1 for keyword in found)
        return found, min(weighted / 8.0, 1.0)

    def insurer_candidates(
        self, text: str, words: list[PDFWord], page_number: int,
    ) -> list[ExtractionCandidate]:
        values = {name for name in self.insurers if name.casefold() in text.casefold()}
        values = {
            value for value in values
            if not any(value != other and value.casefold() in other.casefold() for other in values)
        }
        # 목록 밖 보험사도 회사형 suffix와 명시적 header 문맥이 있으면 후보로만 보존한다.
        if any(header in text for header in self.insurer_headers):
            values.update(re.findall(r"[가-힣A-Za-z()]{2,30}(?:손해보험|생명|화재)", text))
        results = []
        for value in sorted(values, key=lambda item: (-len(item), item)):
            known = value in self.insurers
            results.append(ExtractionCandidate(
                value=value, page_number=page_number, bbox=_bbox_for_text(words, value),
                confidence=Confidence.HIGH if known else Confidence.MEDIUM,
                confidence_reason="설정된 보험사 명칭과 일치" if known else "보험회사 header 주변의 회사형 명칭",
            ))
        return results

    def product_candidates(
        self, text: str, words: list[PDFWord], page_number: int,
    ) -> list[ExtractionCandidate]:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        values: dict[str, tuple[Confidence, str]] = {}
        for index, line in enumerate(lines):
            if line.replace(" ", "") in {"상품명", "보험상품명"} and index + 1 < len(lines):
                candidate = lines[index + 1]
                if 2 <= len(candidate) <= 150:
                    values[candidate] = (Confidence.HIGH, "상품명 header의 다음 행")
            if any(keyword.casefold() in line.casefold() for keyword in self.product_keywords):
                values.setdefault(line, (Confidence.HIGH, "치아보험 상품 키워드 포함"))
            elif ("(무)" in line or "무배당" in line) and "보험" in line:
                values.setdefault(line, (Confidence.MEDIUM, "보험 상품명 형태와 일치"))
        return [
            ExtractionCandidate(value, page_number, _bbox_for_text(words, value), confidence, reason)
            for value, (confidence, reason) in values.items()
        ]
