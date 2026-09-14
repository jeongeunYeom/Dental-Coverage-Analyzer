from __future__ import annotations

from datetime import date
import re

from dental_coverage_analyzer.core.money import parse_money
from dental_coverage_analyzer.models import (
    Confidence,
    EffectiveTextSource,
    InsuranceContract,
    PDFDocumentData,
    PageType,
    SourceReference,
    ValidationIssue,
    ValidationSeverity,
)
from dental_coverage_analyzer.core.pdf.table_layout import build_rows

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
            text = page.effective_text or page.text
            starts = [match.start() for match in re.finditer(r"(?:^|\n)\s*(?:보험회사|보험사)\s*[:：]", text)]
            segments = []
            if starts:
                segments = [
                    text[start:(starts[index + 1] if index + 1 < len(starts) else len(text))]
                    for index, start in enumerate(starts)
                ]
            else:
                segments = [text]
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
                if page.effective_source is EffectiveTextSource.OCR:
                    confidence = Confidence.MEDIUM if page.confidence is not Confidence.LOW else Confidence.LOW
                elif page.ocr_required:
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
            contracts.extend(_matrix_contracts(page))
        items, issues = self._deduplicate(contracts)
        return ParserOutput(items, issues)

    @staticmethod
    def _deduplicate(
        contracts: list[InsuranceContract],
    ) -> tuple[list[InsuranceContract], list[ValidationIssue]]:
        merged: dict[tuple, InsuranceContract] = {}
        identities: dict[tuple[str | None, str | None], set[tuple]] = {}
        for contract in contracts:
            distinguishing = (
                contract.enrollment_date, contract.coverage_period, contract.insured_person,
            )
            # 식별 필드가 하나도 없으면 서로 다른 페이지의 동일 상품을 한 계약으로 추측하지 않는다.
            source_scope = None if any(value is not None for value in distinguishing) else tuple(
                source.page for source in contract.sources
            )
            key = (
                contract.insurer, contract.product_name, contract.enrollment_date,
                contract.coverage_period, contract.insured_person, source_scope,
            )
            identities.setdefault((contract.insurer, contract.product_name), set()).add(key[2:])
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
        issues = [
            ValidationIssue(
                "CONTRACT_IDENTITY_CONFLICT", ValidationSeverity.WARNING,
                "동일 보험사·상품명에서 서로 다른 계약 식별정보가 발견되었습니다",
                sorted({source.page for item in merged.values() if (item.insurer, item.product_name) == base for source in item.sources}),
                "InsuranceContract", "|".join(value or "" for value in base),
                [str(identity) for identity in values],
            )
            for base, values in identities.items() if len(values) > 1
        ]
        return list(merged.values()), issues


def _matrix_contracts(page) -> list[InsuranceContract]:
    """bbox header/cell 근거가 있는 가로형 계약표만 보수적으로 추출한다."""
    rows = build_rows(page.effective_words or page.words, page.height)
    results: list[InsuranceContract] = []
    for index, header in enumerate(rows):
        labels: dict[str, float] = {}
        for word in header.words:
            compact = word.text.replace(" ", "")
            key = next((name for name, aliases in {
                "insurer": ("보험회사", "보험사"), "product": ("상품명", "보험상품명"),
                "period": ("보험기간",), "premium": ("월보험료", "보험료"),
                "enrollment": ("보험가입일", "가입일"),
            }.items() if compact in aliases), None)
            if key:
                labels[key] = (word.x0 + word.x1) / 2
        if not {"insurer", "product"}.issubset(labels):
            continue
        for row in rows[index + 1:]:
            if row.center_y - header.center_y > page.height * 0.25:
                break
            cells: dict[str, list[str]] = {key: [] for key in labels}
            for word in row.words:
                center = (word.x0 + word.x1) / 2
                key = min(labels, key=lambda name: abs(labels[name] - center))
                cells[key].append(word.text)
            insurer = _valid_insurer(" ".join(cells["insurer"]).strip())
            product = _valid_product(" ".join(cells["product"]).strip())
            if not insurer or not product:
                continue
            premium_raw = " ".join(cells.get("premium", [])).strip() or None
            premium = parse_money(premium_raw)
            results.append(InsuranceContract(
                insurer=insurer, product_name=product,
                enrollment_date=_date(" ".join(cells.get("enrollment", []))),
                coverage_period=" ".join(cells.get("period", [])).strip() or None,
                monthly_premium=premium.value if premium else None,
                sources=[SourceReference(page.page_number, row.bbox, row.text)],
                confidence=Confidence.HIGH if not page.ocr_required else Confidence.LOW,
                confidence_reason="계약표 header와 동일 행 cell의 bbox 열 관계",
            ))
    return results or _vertical_matrix_contracts(page, rows)


def _vertical_matrix_contracts(page, rows) -> list[InsuranceContract]:
    """각 field가 행이고 여러 계약이 열인 matrix는 cell 개수가 일치할 때만 읽는다."""
    aliases = {
        "insurer": {"보험회사", "보험사"}, "product": {"상품명", "보험상품명"},
        "period": {"보험기간"}, "premium": {"월보험료", "보험료"},
        "enrollment": {"보험가입일", "가입일"},
    }
    fields: dict[str, tuple] = {}
    for row in rows:
        if len(row.words) < 2:
            continue
        label = row.words[0].text.replace(" ", "")
        key = next((name for name, values in aliases.items() if label in values), None)
        if key:
            fields[key] = row.words[1:]
    if not {"insurer", "product"}.issubset(fields):
        return []
    count = len(fields["insurer"])
    if count == 0 or len(fields["product"]) != count:
        return []
    results = []
    for index in range(count):
        insurer = _valid_insurer(fields["insurer"][index].text)
        product = _valid_product(fields["product"][index].text)
        if not insurer or not product:
            continue
        premium_raw = fields.get("premium", ())[index].text if len(fields.get("premium", ())) == count else None
        premium = parse_money(premium_raw)
        period = fields.get("period", ())[index].text if len(fields.get("period", ())) == count else None
        enrollment = fields.get("enrollment", ())[index].text if len(fields.get("enrollment", ())) == count else None
        related_words = [values[index] for values in fields.values() if len(values) == count]
        bbox = (
            min(word.x0 for word in related_words), min(word.y0 for word in related_words),
            max(word.x1 for word in related_words), max(word.y1 for word in related_words),
        )
        results.append(InsuranceContract(
            insurer=insurer, product_name=product, enrollment_date=_date(enrollment),
            coverage_period=period, monthly_premium=premium.value if premium else None,
            sources=[SourceReference(page.page_number, bbox, " | ".join(word.text for word in related_words))],
            confidence=Confidence.HIGH if not page.ocr_required else Confidence.LOW,
            confidence_reason="열 방향 계약 matrix의 bbox 정렬과 동일 cell 개수",
        ))
    return results
