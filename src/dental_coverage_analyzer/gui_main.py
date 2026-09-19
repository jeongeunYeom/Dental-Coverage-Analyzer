import sys
import os

from dental_coverage_analyzer.core.pdf import OCRAvailability, check_ocr_availability
from dental_coverage_analyzer.core.resources import load_config


def health_check() -> int:
    try:
        load_config("ocr_settings.json")
        health = check_ocr_availability(require_bundled=True)
    except Exception as exc:
        _emit(f"APP_ERROR: {exc}")
        return 2
    _emit("APP_OK")
    _emit("OCR_OK" if health.status is OCRAvailability.AVAILABLE else f"OCR_{health.status}: {health.reason}")
    return 0 if health.status is OCRAvailability.AVAILABLE else 3


def _emit(message: str) -> None:
    if sys.stdout is not None:
        print(message, flush=True)


def _attach_parent_console() -> None:
    """Expose health-check output from the normal windowed Windows executable."""
    if os.name != "nt" or sys.stdout is not None:
        return
    try:
        import ctypes
        ctypes.windll.kernel32.AttachConsole(-1)
        sys.stdout = open("CONOUT$", "w", encoding="utf-8", buffering=1)
        sys.stderr = open("CONOUT$", "w", encoding="utf-8", buffering=1)
    except (OSError, AttributeError):
        pass


if __name__ == "__main__":
    if "--health-check" in sys.argv:
        _attach_parent_console()
        raise SystemExit(health_check())
    from dental_coverage_analyzer.ui import run_gui
    raise SystemExit(run_gui())
