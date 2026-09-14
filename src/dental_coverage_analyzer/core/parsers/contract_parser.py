from __future__ import annotations

from datetime import date
import re

from dental_coverage_analyzer.core.money import parse_money
from dental_coverage_analyzer.models import (
    Confidence,
    InsuranceContract,
    PDFDocumentData,
    PageType,
    SourceReference,
)

from .base import ParserOutput


_PAGE_TYPES = {PageType.CONTRACT_LIST, PageType.PRODUCT_MATRIX, PageType.PRODUCT_DETAIL}


def _field(text: str, *labels: str) -> str | None:
    alternatives = "|".join(re.escape(label) for label in labels)
    match = re.search(
        rf"(?:^|\n)\s*(?:{alternatives})\s*[:：]?\s*(?:\n\s*)?([^\n|]+)",
        text,
        re.MULTILINE,
    )
    value = match.group(1).strip() if match else None
    return value or None


def _date(value: str | None) -> date | None:
    if not value:
        return None
    match = re.search(r"\d{4}-\d{2}-\d{2}", value)
    if not match:
        return None
    try:
        return date.fromisoformat(match.group(0))
    except ValueError:
        return None


def _valid_insurer(value: str | None) -> str | None:
    if not value or any(header in value for header in ("담보 이름", "상품명", "가입금액", "보험기간")):
        return None
    return value if re.search(r"보험|생명|화재", value) else None


def _valid_product(value: str | None) -> str | None:
    if not value or value.replace(" ", "") in {"보험기간", "가입금액", "월보험료", "담보이름"}:
        return None
    return value if len(value) <= 150 else None


class InsuranceContractParser:
    def parse(self, document: PDFDocumentData) -> ParserOutput:
        contracts: list[InsuranceContract] = []
        for page in document.pages:
            if page.page_type not in _PAGE_TYPES:
                continue
            starts = [match.start() for match in re.finditer(r"(?:^|\n)\s*(?:보험회사|보험사)\s*[:：]", page.text)]
            segments = []
            if starts:
                segments = [
                    page.text[start:(starts[index + 1] if index + 1 < len(starts) else len(page.text))]
                    for index, start in enumerate(starts)
                ]
            else:
                segments = [page.text]
            for segment in segments:
                insurer = _valid_insurer(_field(segment, "보험회사", "보험사"))
                product = _valid_product(_field(segment, "보험상품명", "상품명"))
                if not insurer and len(segments) == 1 and page.insurer_candidates:
                    insurer = page.insurer_candidates[0].value
                if not product and len(segments) == 1 and page.product_candidates:
                    product = page.product_candidates[0].value
                if not insurer and not product:
                    continue
                premium_raw = _field(segment, "월보험료", "보험료")
                parsed_premium = parse_money(premium_raw)
                confidence = Confidence.HIGH if insurer and product else Confidence.MEDIUM
                if page.ocr_required:
                    confidence = Confidence.LOW
                contracts.append(InsuranceContract(
                    insurer=insurer,
                    product_name=product,
                    policyholder=_field(segment, "계약자"),
                    insured_person=_field(segment, "피보험자"),
                    enrollment_date=_date(_field(segment, "보험가입일", "가입일")),
                    coverage_period=_field(segment, "보험기간"),
                    payment_period=_field(segment, "납입기간"),
                    payment_cycle=_field(segment, "납입주기"),
                    maturity=_field(segment, "만기"),
                    monthly_premium=parsed_premium.value if parsed_premium else None,
                    contract_status=_field(segment, "계약상태", "상태"),
                    sources=[SourceReference(page.page_number, raw_text=segment)],
                    confidence=confidence,
                    confidence_reason=(
                        "명시적 보험사와 상품명" if confidence is Confidence.HIGH
                        else "일부 계약 식별자만 확인되었거나 OCR이 필요함"
                    ),
                ))
        return ParserOutput(self._deduplicate(contracts), [])

    @staticmethod
    def _deduplicate(contracts: list[InsuranceContract]) -> list[InsuranceContract]:
        merged: dict[tuple[str | None, str | None], InsuranceContract] = {}
        for contract in contracts:
            key = contract.insurer, contract.product_name
            if key not in merged:
                merged[key] = contract
                continue
            current = merged[key]
            current.sources.extend(source for source in contract.sources if source not in current.sources)
            for name in (
                "policyholder", "insured_person", "enrollment_date", "coverage_period",
                "payment_period", "payment_cycle", "maturity", "monthly_premium", "contract_status",
            ):
                if getattr(current, name) is None:
                    setattr(current, name, getattr(contract, name))
        return list(merged.values())
