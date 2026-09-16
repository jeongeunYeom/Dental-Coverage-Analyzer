import importlib

import pytest


def test_gui_package_is_lazy_importable_without_qt_runtime():
    module = importlib.import_module("dental_coverage_analyzer.ui")
    assert callable(module.run_gui)


def test_gui_window_import_smoke(monkeypatch):
    pytest.importorskip("PySide6", reason="PySide6가 필요한 GUI import smoke test")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    module = importlib.import_module("dental_coverage_analyzer.ui.app")
    assert module.APP_TITLE == "치아보험 보장분석표 생성기"


def test_gui_summary_uses_two_canonical_rows_for_four_raw_candidates(tmp_path, monkeypatch):
    pytest.importorskip("PySide6", reason="PySide6가 필요한 GUI canonical regression test")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QFrame
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
    summary = window._summary_tab()

    assert window.aggregate_table.rowCount() == 2
    assert len([frame for frame in summary.findChildren(QFrame) if frame.objectName() == "card"]) == 2
    window.close()
    del app
