from __future__ import annotations

import re

from dental_coverage_analyzer.core.money import parse_money
from dental_coverage_analyzer.core.processing import AggregateValidity, assess_aggregate
from dental_coverage_analyzer.models import (
    AggregateCoverage,
    Confidence,
    EffectiveTextSource,
    PDFDocumentData,
    PageType,
    SourceReference,
    ValidationIssue,
    ValidationSeverity,
)

from .base import ParserOutput


_PAGE_TYPES = {
    PageType.COVERAGE_ANALYSIS, PageType.COVERAGE_DETAIL, PageType.DIAGNOSIS_DETAIL,
    PageType.SUMMARY, PageType.ONE_PAGE_SUMMARY,
}
_NAME = re.compile(r"치아\s*(?:보철|보존)(?:\s*치료비)?(?![가-힣])")
_AMOUNT = r"[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?\s*(?:억\s*(?:\d[\d,]*(?:\.\d+)?\s*만(?:원)?)?|만(?:원)?|원)"
_AMOUNT_RE = re.compile(_AMOUNT)
_CELL_AMOUNT_RE = re.compile(rf"{_AMOUNT}|(?<![\d,])[+-]?0(?![\d,])")
_STATUS_RE = re.compile(r"미가입|부족|충분|적정|초과")


def _normalize_name(value: str) -> str:
    return re.sub(r"\s+", "", value)


def _normalize_status(raw: str | None, recommended: int | None, enrolled: int | None) -> str:
    if raw == "미가입" or (enrolled == 0 and recommended is not None and recommended > 0):
        return "NOT_ENROLLED"
    if raw == "부족":
        return "INSUFFICIENT"
    if raw in {"충분", "적정"}:
        return "SUFFICIENT"
    if raw == "초과":
        return "SURPLUS"
    if recommended is not None and enrolled is not None:
        if enrolled < recommended:
            return "INSUFFICIENT"
        if enrolled > recommended:
            return "SURPLUS"
        return "SUFFICIENT"
    return "UNKNOWN"


def _table_unit(text: str) -> str | None:
    match = re.search(r"단위\s*[:：]?\s*(억원|만원|억|만|원)", text)
    return match.group(1) if match else None


def _value(raw: str | None, inherited_unit: str | None = None) -> int | None:
    if raw is None:
        return None
    if raw.strip() in {"0", "+0", "-0"}:
        return 0
    parsed = parse_money(raw)
    if parsed:
        return parsed.value
    if inherited_unit and re.fullmatch(r"[+-]?[\d,.]+", raw.strip()):
        parsed = parse_money(raw.strip() + inherited_unit)
        return parsed.value if parsed else None
    return None


def _labeled(segment: str, labels: str) -> tuple[str | None, int | None]:
    match = re.search(rf"(?:{labels})\s*[:：]?\s*({_AMOUNT}|[+-]?0)(?![\d,])", segment)
    if not match:
        return None, None
    raw = match.group(1).strip()
    return raw, _value(raw)


def _layout_amounts(page, normalized_name: str, inherited_unit: str | None) -> dict[str, tuple[str, int]]:
    """동일 line의 cell을 header x 좌표에 대응한다. 근거가 부족하면 빈 결과다."""
    lines: dict[tuple[int, int], list] = {}
    for word in page.effective_words or page.words:
        lines.setdefault((word.block_no, word.line_no), []).append(word)
    header_columns: dict[str, float] = {}
    for words in lines.values():
        joined = "".join(word.text.replace(" ", "") for word in sorted(words, key=lambda item: item.x0))
        if "권장" not in joined or "가입" not in joined:
            continue
        for word in words:
            compact = word.text.replace(" ", "")
            if "권장" in compact:
                header_columns["recommended"] = (word.x0 + word.x1) / 2
            elif "가입" in compact and "권장" not in compact:
                header_columns["enrolled"] = (word.x0 + word.x1) / 2
            elif "부족" in compact or "과부족" in compact or "차액" in compact:
                header_columns["difference"] = (word.x0 + word.x1) / 2
    if not {"recommended", "enrolled"}.issubset(header_columns):
        return {}
    for words in lines.values():
        ordered = sorted(words, key=lambda item: item.x0)
        joined = "".join(word.text.replace(" ", "") for word in ordered)
        if normalized_name not in joined:
            continue
        values: dict[str, tuple[str, int]] = {}
        for word in ordered:
            raw = word.text.strip()
            value = _value(raw, inherited_unit)
            if value is None:
                continue
            center = (word.x0 + word.x1) / 2
            column = min(header_columns, key=lambda name: abs(header_columns[name] - center))
            values[column] = (raw, value)
        if {"recommended", "enrolled"}.issubset(values):
            return values
    return {}


def _row_bbox(page, normalized_name: str) -> tuple[float, float, float, float] | None:
    lines: dict[tuple[int, int], list] = {}
    for word in page.effective_words or page.words:
        lines.setdefault((word.block_no, word.line_no), []).append(word)
    for words in lines.values():
        joined = "".join(word.text.replace(" ", "") for word in words)
        if normalized_name in joined:
            return (
                min(word.x0 for word in words), min(word.y0 for word in words),
                max(word.x1 for word in words), max(word.y1 for word in words),
            )
    return None


class AggregateCoverageParser:
    """명시적 label 또는 검증된 table header가 있는 치아 집계 행만 파싱한다."""

    def parse(self, document: PDFDocumentData) -> ParserOutput:
        candidates: list[AggregateCoverage] = []
        issues: list[ValidationIssue] = []
        for page in document.pages:
            if page.page_type not in _PAGE_TYPES:
                continue
            text = page.effective_text or page.text
            matches = list(_NAME.finditer(text))
            if not matches:
                continue
            unit = _table_unit(text)
            header_text = text[:matches[0].start()]
            header_labels = [
                label for label in ("권장", "가입", "부족", "과부족")
                if label in header_text
            ]
            for index, match in enumerate(matches):
                end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
                segment = text[match.start():end].strip()
                raw_name = match.group(0).strip()
                recommended_raw, recommended = _labeled(segment, r"권장(?:\s*가입)?금액|권장")
                enrolled_segment = re.sub(
                    rf"권장\s*가입금액\s*[:：]?\s*(?:{_AMOUNT}|[+-]?0)", "", segment,
                )
                enrolled_raw, enrolled = _labeled(
                    enrolled_segment, r"현재\s*가입금액|현재\s*가입|가입금액|가입",
                )
                difference_raw, difference = _labeled(segment, r"부족(?:금액)?|과부족|차액")
                evidence = "명시적 필드 label"

                if recommended is None or enrolled is None:
                    layout = _layout_amounts(page, _normalize_name(raw_name), unit)
                    if layout:
                        recommended_raw, recommended = layout["recommended"]
                        enrolled_raw, enrolled = layout["enrolled"]
                        difference_raw, difference = layout.get("difference", (None, None))
                        evidence = "동일 행 cell과 header의 bbox 열 관계"

                if recommended is None or enrolled is None:
                    amounts = [
                        item.group(0).strip()
                        for item in _CELL_AMOUNT_RE.finditer(segment[match.end() - match.start():])
                    ]
                    # 위치 기반 대응은 header가 두 개 이상 명시된 표에서만 허용한다.
                    if len(header_labels) >= 2 and len(amounts) >= 2:
                        mapped = dict(zip(header_labels, amounts))
                        recommended_raw = mapped.get("권장")
                        enrolled_raw = mapped.get("가입")
                        difference_raw = mapped.get("부족") or mapped.get("과부족")
                        recommended = _value(recommended_raw, unit)
                        enrolled = _value(enrolled_raw, unit)
                        difference = _value(difference_raw, unit)
                        evidence = "표 header와 행의 열 순서"

                # 명시적인 표 단위가 있을 때만 단위 없는 cell을 상속한다.
                if unit and len(header_labels) >= 2 and (recommended is None or enrolled is None):
                    bare = re.findall(r"(?<![\d,.])[+-]?(?:\d[\d,]*(?:\.\d+)?)(?!\s*(?:억|만|원)|[\d,.])", segment)
                    if len(bare) >= 2:
                        recommended_raw, enrolled_raw = bare[:2]
                        difference_raw = bare[2] if len(bare) >= 3 else None
                        recommended = _value(recommended_raw, unit)
                        enrolled = _value(enrolled_raw, unit)
                        difference = _value(difference_raw, unit)
                        evidence = f"명시된 표 단위({unit}) 상속"

                if recommended is None and enrolled is None:
                    continue
                status_match = _STATUS_RE.search(segment)
                raw_status = status_match.group(0) if status_match else None
                normalized_shortage = None
                normalized_surplus = None
                ratio_match = re.search(r"(?:보장률|가입률)\s*[:：]?\s*([\d.]+)\s*%", segment)
                reported_ratio = float(ratio_match.group(1)) if ratio_match else None
                if recommended is not None and enrolled is not None:
                    normalized_shortage = max(recommended - enrolled, 0)
                    normalized_surplus = max(enrolled - recommended, 0)
                if difference is not None and recommended is not None and enrolled is not None:
                    expected = abs(enrolled - recommended)
                    if abs(difference) != expected:
                        issues.append(ValidationIssue(
                            "DIFFERENCE_MISMATCH", ValidationSeverity.WARNING,
                            "원문 차액과 권장/가입금액으로 계산한 차액이 다릅니다",
                            [page.page_number], "AggregateCoverage", _normalize_name(raw_name),
                            [difference_raw or "", str(expected)],
                        ))
                calculated_ratio = (
                    enrolled / recommended * 100
                    if recommended is not None and recommended > 0 and enrolled is not None else None
                )
                if (
                    reported_ratio is not None and calculated_ratio is not None
                    and abs(reported_ratio - calculated_ratio) > 0.1
                ):
                    issues.append(ValidationIssue(
                        "COVERAGE_RATIO_MISMATCH", ValidationSeverity.WARNING,
                        "PDF 보장률과 권장/가입금액으로 계산한 보장률이 다릅니다",
                        [page.page_number], "AggregateCoverage", _normalize_name(raw_name),
                        [str(reported_ratio), str(calculated_ratio)],
                    ))
                confidence_reason = (
                    f"OCR 기반; {evidence}; page_type={page.page_type.value}"
                    if page.effective_source is EffectiveTextSource.OCR
                    else f"{evidence}; page_type={page.page_type.value}"
                    if not page.ocr_required else "OCR 필요 페이지의 Text Layer 결과"
                )
                candidate = AggregateCoverage(
                    raw_name=raw_name,
                    normalized_name=_normalize_name(raw_name),
                    category="보철치료" if "보철" in raw_name else "보존치료",
                    recommended_amount=recommended,
                    enrolled_amount=enrolled,
                    shortage_amount=difference if raw_status in {"부족", "미가입"} else None,
                    surplus_amount=difference if raw_status == "초과" else None,
                    raw_difference=difference_raw,
                    normalized_shortage=normalized_shortage,
                    normalized_surplus=normalized_surplus,
                    reported_ratio=reported_ratio,
                    calculated_ratio=calculated_ratio,
                    status=raw_status,
                    normalized_status=_normalize_status(raw_status, recommended, enrolled),
                    source_pages=[page.page_number],
                    representative_source=SourceReference(
                        page.page_number, _row_bbox(page, _normalize_name(raw_name)), segment,
                    ),
                    confidence=Confidence.MEDIUM,
                    confidence_reason=confidence_reason,
                )
                assessment = assess_aggregate(candidate)
                # HIGH는 완전하고 논리적으로 유효한 bbox header-cell 근거에만 허용한다.
                if assessment.validity is AggregateValidity.VALID and evidence == "동일 행 cell과 header의 bbox 열 관계":
                    candidate.confidence = Confidence.HIGH
                elif assessment.validity is not AggregateValidity.VALID:
                    candidate.confidence = Confidence.LOW
                    code = "AGGREGATE_INCOMPLETE" if assessment.validity is AggregateValidity.INCOMPLETE else "AGGREGATE_LOGIC_INVALID"
                    issues.append(ValidationIssue(
                        code, ValidationSeverity.WARNING,
                        f"'{raw_name}' 후보를 대표값으로 확정하기 어렵습니다: {assessment.reason}",
                        [page.page_number], "AggregateCoverage", _normalize_name(raw_name),
                        [
                            f"권장={recommended}", f"가입={enrolled}",
                            f"부족={difference}", f"상태={raw_status}",
                        ],
                    ))
                if page.effective_source is EffectiveTextSource.OCR:
                    if candidate.confidence is Confidence.HIGH:
                        candidate.confidence = Confidence.MEDIUM
                    if page.confidence is Confidence.LOW:
                        candidate.confidence = Confidence.LOW
                elif page.ocr_required:
                    candidate.confidence = Confidence.LOW
                candidates.append(candidate)
        deduplicated, duplicate_issues = deduplicate_aggregate_coverages(candidates)
        return ParserOutput(deduplicated, issues + duplicate_issues)


def deduplicate_aggregate_coverages(
    candidates: list[AggregateCoverage],
) -> tuple[list[AggregateCoverage], list[ValidationIssue]]:
    results: list[AggregateCoverage] = []
    issues: list[ValidationIssue] = []
    by_name: dict[str, list[AggregateCoverage]] = {}
    for item in candidates:
        by_name.setdefault(item.normalized_name or item.raw_name, []).append(item)
    for name, group in by_name.items():
        signatures: dict[tuple, list[AggregateCoverage]] = {}
        for item in group:
            signature = item.recommended_amount, item.enrolled_amount
            signatures.setdefault(signature, []).append(item)
        for identical in signatures.values():
            primary = identical[0]
            primary.source_pages = sorted({page for item in identical for page in item.source_pages})
            results.append(primary)
        if len(signatures) > 1:
            pages = sorted({page for item in group for page in item.source_pages})
            issues.append(ValidationIssue(
                "AGGREGATE_AMOUNT_CONFLICT", ValidationSeverity.WARNING,
                f"동일 집계 담보 '{name}'의 페이지별 값이 서로 다릅니다",
                pages, "AggregateCoverage", name,
                [f"권장={item.recommended_amount},가입={item.enrolled_amount}" for item in group],
            ))
    return results, issues
