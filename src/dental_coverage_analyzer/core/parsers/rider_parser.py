from __future__ import annotations

import json
from pathlib import Path
import re

from dental_coverage_analyzer.core.dental import (
    DentalCategoryClassifier,
    DentalProductDetector,
    extract_cause_type,
    extract_payment_unit,
)
from dental_coverage_analyzer.core.money import parse_money
from dental_coverage_analyzer.core.resources import config_path
from dental_coverage_analyzer.models import (
    Confidence,
    DentalRider,
    InsuranceContract,
    PDFDocumentData,
    PageType,
    SourceReference,
    ValidationIssue,
    ValidationSeverity,
)

from .base import ParserOutput


_PAGE_TYPES = {PageType.PRODUCT_DETAIL, PageType.PRODUCT_MATRIX}
_AMOUNT_RE = re.compile(
    r"[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?\s*(?:억\s*(?:\d[\d,]*(?:\.\d+)?\s*만(?:원)?)?|만(?:원)?|원)"
)


def _line_bbox(page, line: str) -> tuple[float, float, float, float] | None:
    tokens = {token.casefold() for token in line.split() if token}
    matches = [word for word in page.words if word.text.casefold() in tokens]
    if not matches:
        return None
    return (
        min(word.x0 for word in matches), min(word.y0 for word in matches),
        max(word.x1 for word in matches), max(word.y1 for word in matches),
    )


class DentalRiderParser:
    def __init__(self, keywords_file: str | Path | None = None) -> None:
        path = Path(keywords_file) if keywords_file else config_path("dental_keywords.json")
        with path.open(encoding="utf-8") as stream:
            config = json.load(stream)
        self.keywords: list[str] = sorted(config["include"], key=len, reverse=True)
        self.exclusions: list[str] = config["exclude"]
        self.category_classifier = DentalCategoryClassifier()
        self.product_detector = DentalProductDetector()

    def parse(
        self, document: PDFDocumentData, contracts: list[InsuranceContract],
    ) -> ParserOutput:
        riders: list[DentalRider] = []
        issues: list[ValidationIssue] = []
        contracts_by_page: dict[int, list[InsuranceContract]] = {}
        for candidate in contracts:
            for source in candidate.sources:
                contracts_by_page.setdefault(source.page, []).append(candidate)
        previous_contract: InsuranceContract | None = None
        previous_page = -2
        for page in document.pages:
            if page.page_type not in _PAGE_TYPES:
                continue
            page_contracts = contracts_by_page.get(page.page_number, [])
            # 동일 페이지에 여러 계약이 있고 표 영역 연결이 없으면 하나를 임의 선택하지 않는다.
            contract = page_contracts[0] if len(page_contracts) == 1 else None
            inherited = False
            if contract is None and previous_contract is not None and page.page_number == previous_page + 1:
                if self.product_detector.detect(previous_contract.product_name).is_candidate:
                    contract = previous_contract
                    inherited = True
            if contract is not None:
                previous_contract, previous_page = contract, page.page_number

            for line in (line.strip() for line in page.text.splitlines() if line.strip()):
                if any(exclusion in line for exclusion in self.exclusions):
                    continue
                amounts = list(_AMOUNT_RE.finditer(line))
                if not amounts:
                    continue
                amount_match = amounts[-1]
                parsed = parse_money(amount_match.group(0).strip())
                if not parsed:
                    continue
                before_amount = line[:amount_match.start()].strip(" /|\t")
                parts = [part.strip() for part in re.split(r"\s*(?:/|\||\t)\s*", before_amount) if part.strip()]
                raw_name = parts[0] if parts else before_amount
                credit_name = parts[1] if len(parts) > 1 else None
                matched = [keyword for keyword in self.keywords if keyword.casefold() in raw_name.casefold()]
                specific = [keyword for keyword in matched if keyword not in {"치아", "치과", "구강"}]
                # 상품명 자체나 일반 보험 필드는 담보로 오인하지 않는다.
                if not matched or ("치아보험" in raw_name and not specific):
                    continue
                confidence = Confidence.HIGH if specific and contract and not inherited else Confidence.MEDIUM
                reason = "원본 담보명의 치아 키워드와 동일 페이지 상품 context"
                if not contract:
                    confidence = Confidence.LOW
                    reason = "치아 담보명은 확인했으나 계약 연결 근거가 없음"
                    issues.append(ValidationIssue(
                        "CONTRACT_LINK_UNCERTAIN", ValidationSeverity.WARNING,
                        f"담보 '{raw_name}'의 보험상품 연결을 확인해야 합니다",
                        [page.page_number], "DentalRider", raw_name, [line],
                    ))
                elif inherited:
                    confidence = Confidence.MEDIUM
                    reason = "직전 연속 상품 상세 페이지의 검증된 치아보험 context"
                if page.ocr_required:
                    confidence = Confidence.LOW
                    reason = "OCR 필요 페이지의 Text Layer에서 추출"
                rider = DentalRider(
                    raw_name=raw_name,
                    insurer=contract.insurer if contract else None,
                    product_name=contract.product_name if contract else None,
                    normalized_name="".join(raw_name.split()),
                    credit_information_name=credit_name,
                    category=self.category_classifier.classify(raw_name),
                    enrolled_amount=parsed.value,
                    raw_amount=parsed.raw,
                    payment_unit=extract_payment_unit(line),
                    cause_type=extract_cause_type(raw_name),
                    source=SourceReference(page.page_number, _line_bbox(page, line), line),
                    confidence=confidence,
                    confidence_reason=reason,
                    raw_text=line,
                )
                riders.append(rider)
                if confidence is Confidence.LOW:
                    issues.append(ValidationIssue(
                        "LOW_CONFIDENCE_RIDER", ValidationSeverity.WARNING,
                        f"낮은 confidence 담보 '{raw_name}'를 확인해야 합니다",
                        [page.page_number], "DentalRider", raw_name, [line],
                    ))
        return ParserOutput(riders, issues)
