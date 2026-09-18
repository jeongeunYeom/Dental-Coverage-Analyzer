from __future__ import annotations

from dataclasses import dataclass
from statistics import median

from dental_coverage_analyzer.models import PDFWord


@dataclass(frozen=True, slots=True)
class LayoutRow:
    words: tuple[PDFWord, ...]
    text: str
    bbox: tuple[float, float, float, float]
    center_y: float


@dataclass(frozen=True, slots=True)
class ColumnCandidate:
    x_center: float
    word_count: int


def build_rows(words: list[PDFWord], page_height: float, tolerance: float | None = None) -> list[LayoutRow]:
    """미세하게 다른 y 좌표를 word 높이와 페이지 크기에 비례해 시각 행으로 묶는다."""
    if not words:
        return []
    heights = [max(word.y1 - word.y0, 1.0) for word in words]
    y_tolerance = tolerance if tolerance is not None else max(1.5, min(median(heights) * 0.55, page_height * 0.01))
    ordered = sorted(words, key=lambda word: ((word.y0 + word.y1) / 2, word.x0))
    groups: list[list[PDFWord]] = []
    centers: list[float] = []
    for word in ordered:
        center = (word.y0 + word.y1) / 2
        target = next((i for i, value in enumerate(centers) if abs(center - value) <= y_tolerance), None)
        if target is None:
            groups.append([word])
            centers.append(center)
        else:
            groups[target].append(word)
            centers[target] = sum((item.y0 + item.y1) / 2 for item in groups[target]) / len(groups[target])
    rows = []
    for group, center in sorted(zip(groups, centers), key=lambda item: item[1]):
        line = tuple(sorted(group, key=lambda word: word.x0))
        rows.append(LayoutRow(
            line,
            " ".join(word.text for word in line),
            (min(w.x0 for w in line), min(w.y0 for w in line), max(w.x1 for w in line), max(w.y1 for w in line)),
            center,
        ))
    return rows


def infer_columns(rows: list[LayoutRow], x_tolerance: float = 24.0) -> list[ColumnCandidate]:
    centers: list[list[float]] = []
    for row in rows:
        for word in row.words:
            center = (word.x0 + word.x1) / 2
            group = next((item for item in centers if abs(sum(item) / len(item) - center) <= x_tolerance), None)
            if group is None:
                centers.append([center])
            else:
                group.append(center)
    return sorted(
        (ColumnCandidate(sum(group) / len(group), len(group)) for group in centers),
        key=lambda column: column.x_center,
    )

