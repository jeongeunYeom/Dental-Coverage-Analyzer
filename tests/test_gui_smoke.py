import importlib

import pytest


def test_gui_package_is_lazy_importable_without_qt_runtime():
    module = importlib.import_module("dental_coverage_analyzer.ui")
    assert callable(module.run_gui)


def test_gui_window_import_smoke(monkeypatch):
    pytest.importorskip("PySide6", reason="PySide6가 필요한 GUI import smoke test")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    try:
        module = importlib.import_module("dental_coverage_analyzer.ui.app")
    except ImportError as exc:
        pytest.skip(f"Qt system library를 사용할 수 없음: {exc}")
    assert module.APP_TITLE == "치아보험 보장분석표 생성기"


def test_gui_summary_uses_two_canonical_rows_for_four_raw_candidates(tmp_path, monkeypatch):
    pytest.importorskip("PySide6", reason="PySide6가 필요한 GUI canonical regression test")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide6.QtWidgets import QApplication, QFrame
    except ImportError as exc:
        pytest.skip(f"Qt system library를 사용할 수 없음: {exc}")
    from dental_coverage_analyzer.core.pdf.analyzer import PDFAnalysisResult
    from dental_coverage_analyzer.models import PDFDocumentData
    from dental_coverage_analyzer.ui.app import MainWindow
    from dental_coverage_analyzer.ui.session import AnalysisSession
    from test_canonical_aggregates import actual_conflicting_candidates

    app = QApplication.instance() or QApplication([])
    document = PDFDocumentData(tmp_path / "synthetic.pdf", "synthetic.pdf", 0, {}, False, [])
    result = PDFAnalysisResult(document, {}, [], {}, [], [], [])
    result.aggregate_coverages = actual_conflicting_candidates()
    window = MainWindow()
    window.session = AnalysisSession.from_result("synthetic.pdf", result)
    window._build_result_page()
    summary = window.tabs.widget(0)

    assert window.aggregate_table.rowCount() == 2
    assert len([frame for frame in summary.findChildren(QFrame) if frame.objectName() == "card"]) == 2
    assert window.contract_table.rowCount() == 0
    comment = "보철치료 보장이 부족합니다.\n보험증권 확인이 필요합니다."
    window.comment_edit.setPlainText(comment)
    assert window.report_data().comment == comment
    window.close()
    del app
