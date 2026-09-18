from __future__ import annotations

from dataclasses import dataclass

from dental_coverage_analyzer.models import AggregateCoverage, DentalRider, InsuranceContract, SourceReference

from .presentation import confidence_label


@dataclass(frozen=True, slots=True)
class Evidence:
    pages: tuple[int, ...]
    entries: tuple[tuple[int, str], ...]
    confidence: str


def _entries(sources: list[SourceReference]) -> tuple[tuple[int, str], ...]:
    return tuple((source.page, source.raw_text or "원본 문구 정보가 없습니다.") for source in sources)


def aggregate_evidence(item: AggregateCoverage) -> Evidence:
    sources = [item.representative_source] if item.representative_source else []
    pages = tuple(sorted(set(item.source_pages) | {s.page for s in sources}))
    entries = _entries(sources) or tuple((page, "원본 문구 정보가 없습니다.") for page in pages)
    return Evidence(pages, entries, confidence_label(item.confidence))


def contract_evidence(item: InsuranceContract) -> Evidence:
    return Evidence(tuple(sorted({s.page for s in item.sources})), _entries(item.sources), confidence_label(item.confidence))


def rider_evidence(item: DentalRider) -> Evidence:
    sources = list(item.sources)
    if item.source and item.source not in sources:
        sources.append(item.source)
    entries = _entries(sources)
    if item.raw_text and entries:
        entries = tuple((page, text if text != "원본 문구 정보가 없습니다." else item.raw_text) for page, text in entries)
    return Evidence(tuple(sorted({s.page for s in sources})), entries, confidence_label(item.confidence))
