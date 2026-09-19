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
    # Do not schedule modal onboarding/autosave prompts in the non-interactive
    # offscreen test process. Production keeps the default value (True).
    window = MainWindow(enable_startup_prompts=False)
    window.session = AnalysisSession.from_result("synthetic.pdf", result)
    window._build_result_page()
    summary = window.tabs.widget(0)

    assert window.aggregate_table.rowCount() == 2
    assert len([frame for frame in summary.findChildren(QFrame) if frame.objectName() == "card"]) == 2
    assert window.contract_table.rowCount() == 0
    comment = "보철치료 보장이 부족합니다.\n보험증권 확인이 필요합니다."
    window.comment_edit.setPlainText(comment)
    # textChanged must update the session immediately; report generation,
    # autosave, or another dialog must not be required for synchronization.
    assert window.session.comment == comment
    assert window.session.is_dirty is True
    assert window.report_data().comment == comment
    # QTextEdit changes mark the session dirty. Avoid exercising the separate
    # interactive close-confirmation workflow in this rendering smoke test.
    window.session.is_dirty = False
    window.close()
    del app


def test_comment_survives_branding_apply_cancel_and_project_round_trip(tmp_path, monkeypatch):
    pytest.importorskip("PySide6", reason="PySide6가 필요한 GUI comment regression test")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide6.QtWidgets import QApplication
        import dental_coverage_analyzer.ui.app as app_module
    except ImportError as exc:
        pytest.skip(f"Qt system library를 사용할 수 없음: {exc}")
    from dental_coverage_analyzer.branding import BrandingSettings
    from dental_coverage_analyzer.core.pdf.analyzer import PDFAnalysisResult
    from dental_coverage_analyzer.models import PDFDocumentData
    from dental_coverage_analyzer.ui.project_store import load_project, save_project
    from dental_coverage_analyzer.ui.session import AnalysisSession

    qt_app = QApplication.instance() or QApplication([])
    document = PDFDocumentData(tmp_path / "synthetic.pdf", "synthetic.pdf", 0, {}, False, [])
    result = PDFAnalysisResult(document, {}, [], {}, [], [], [])
    window = app_module.MainWindow(enable_startup_prompts=False)
    window.session = AnalysisSession.from_result("synthetic.pdf", result)
    window._build_result_page()
    comment = "보철치료 보장이 부족합니다."
    window.comment_edit.setPlainText(comment)
    assert window.session.comment == comment

    monkeypatch.setattr(app_module, "save_settings", lambda settings: tmp_path / "settings.json")
    window._apply_branding_settings(BrandingSettings("가상 컨설팅", "홍길동"))
    assert window.comment_edit.toPlainText() == comment
    assert window.session.comment == comment

    class CancelledDialog:
        class DialogCode:
            Accepted = 1
        def __init__(self, *_args): pass
        def exec(self): return 0

    monkeypatch.setattr(app_module, "BrandingSettingsDialog", CancelledDialog)
    window.open_branding_settings()
    assert window.comment_edit.toPlainText() == comment
    assert window.session.comment == comment

    destination = tmp_path / "comment.dca"
    save_project(window.session, destination)
    assert load_project(destination).session.comment == comment
    window.session.is_dirty = False
    window.close()
    del qt_app


def test_gui_window_can_process_events_without_modal_startup(monkeypatch):
    pytest.importorskip("PySide6", reason="PySide6가 필요한 GUI startup regression test")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide6.QtWidgets import QApplication
        from dental_coverage_analyzer.ui.app import MainWindow
    except ImportError as exc:
        pytest.skip(f"Qt system library를 사용할 수 없음: {exc}")

    app = QApplication.instance() or QApplication([])
    window = MainWindow(enable_startup_prompts=False)
    app.processEvents()
    assert window.isEnabled()
    window.close()
