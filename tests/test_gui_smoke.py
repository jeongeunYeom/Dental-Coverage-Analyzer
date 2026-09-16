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
