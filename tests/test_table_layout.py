from dental_coverage_analyzer.core.pdf.table_layout import build_rows, infer_columns
from dental_coverage_analyzer.models import PDFWord


def test_rows_use_visual_tolerance_not_exact_y_equality():
    words = [
        PDFWord("치아보철", 10, 100.0, 80, 112, 0, 0, 0),
        PDFWord("200만원", 200, 101.8, 250, 114, 0, 0, 1),
        PDFWord("치아보존", 10, 130, 80, 142, 0, 1, 0),
        PDFWord("50만원", 200, 131.2, 250, 143, 0, 1, 1),
    ]
    rows = build_rows(words, 700)
    assert len(rows) == 2
    assert rows[0].text == "치아보철 200만원"
    assert rows[0].bbox == (10, 100.0, 250, 114)
    columns = infer_columns(rows)
    assert len(columns) == 2
    assert [column.word_count for column in columns] == [2, 2]

