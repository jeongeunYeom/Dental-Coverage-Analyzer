"""PySide6 GUI. PySide6 import는 run_gui 호출 시에만 필요합니다."""


def run_gui() -> int:
    from .app import run_gui as _run_gui
    return _run_gui()


__all__ = ["run_gui"]
