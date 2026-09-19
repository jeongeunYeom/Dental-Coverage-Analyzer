from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import os
from pathlib import Path
import subprocess

from .tesseract_ocr import TesseractOCREngine


class OCRAvailability(StrEnum):
    AVAILABLE = "AVAILABLE"
    NOT_AVAILABLE = "NOT_AVAILABLE"
    BROKEN = "BROKEN"


@dataclass(frozen=True, slots=True)
class OCRHealth:
    status: OCRAvailability
    executable: Path | None = None
    reason: str = ""


def check_ocr_availability(*, require_bundled: bool = False) -> OCRHealth:
    executable = TesseractOCREngine()._resolve()
    if executable is None:
        return OCRHealth(OCRAvailability.NOT_AVAILABLE, reason="문서 인식 실행 파일을 찾지 못했습니다")
    if require_bundled and executable.parent.name.casefold() != "tesseract":
        return OCRHealth(OCRAvailability.NOT_AVAILABLE, executable, "번들 문서 인식 엔진이 아닙니다")
    tessdata = executable.parent / "tessdata"
    missing = [name for name in ("kor.traineddata", "eng.traineddata") if not (tessdata / name).is_file()]
    if missing:
        return OCRHealth(OCRAvailability.BROKEN, executable, "언어 데이터 누락: " + ", ".join(missing))
    environment = os.environ.copy()
    environment["TESSDATA_PREFIX"] = str(tessdata)
    try:
        process = subprocess.run(
            [str(executable), "--version"], capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=15, check=False, env=environment,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return OCRHealth(OCRAvailability.BROKEN, executable, str(exc))
    if process.returncode != 0:
        return OCRHealth(OCRAvailability.BROKEN, executable, process.stderr.strip()[:300])
    return OCRHealth(OCRAvailability.AVAILABLE, executable)
