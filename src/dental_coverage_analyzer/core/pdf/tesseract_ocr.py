from __future__ import annotations

import csv
import io
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from .ocr_engine import OCRResult, OCRStatus, OCRWord


class TesseractOCREngine:
    """다운로드나 네트워크 호출 없이 local Tesseract CLI만 실행한다."""

    def __init__(self, executable: str | Path | None = None, timeout: int = 120) -> None:
        self.explicit_executable = Path(executable).expanduser() if executable else None
        self.timeout = timeout

    def _resolve(self) -> Path | None:
        roots = []
        if getattr(sys, "_MEIPASS", None):
            roots.append(Path(sys._MEIPASS))
        roots.append(Path(__file__).resolve().parents[2] / "resources")
        for root in roots:
            bundled = root / "tesseract" / ("tesseract.exe" if os.name == "nt" else "tesseract")
            if bundled.is_file():
                return bundled
        if self.explicit_executable and self.explicit_executable.is_file():
            return self.explicit_executable
        found = shutil.which("tesseract")
        return Path(found) if found else None

    def recognize(self, image: bytes, languages: tuple[str, ...] = ("kor", "eng")) -> OCRResult:
        executable = self._resolve()
        if executable is None:
            return OCRResult(OCRStatus.NOT_CONFIGURED, reason="로컬 Tesseract 실행 파일을 찾지 못했습니다")
        if not image:
            return OCRResult(OCRStatus.FAILED, reason="OCR 이미지가 비어 있습니다")
        temporary: str | None = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as stream:
                stream.write(image)
                temporary = stream.name
            command = [str(executable), temporary, "stdout", "-l", "+".join(languages), "tsv"]
            environment = os.environ.copy()
            bundled_tessdata = executable.parent / "tessdata"
            if bundled_tessdata.is_dir():
                environment["TESSDATA_PREFIX"] = str(bundled_tessdata)
            process = subprocess.run(
                command, capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=self.timeout, check=False, env=environment,
            )
            if process.returncode != 0:
                status = (
                    OCRStatus.NOT_CONFIGURED
                    if "failed loading language" in process.stderr.casefold() else OCRStatus.FAILED
                )
                return OCRResult(
                    status,
                    reason=(process.stderr.strip() or f"Tesseract 종료 코드 {process.returncode}")[:500],
                )
            words: list[OCRWord] = []
            for row in csv.DictReader(io.StringIO(process.stdout), delimiter="\t"):
                text = (row.get("text") or "").strip()
                try:
                    confidence = float(row.get("conf", "-1"))
                except ValueError:
                    confidence = -1
                if not text or confidence < 0:
                    continue
                left, top = float(row["left"]), float(row["top"])
                width, height = float(row["width"]), float(row["height"])
                words.append(OCRWord(
                    text, (left, top, left + width, top + height), confidence,
                    int(row.get("block_num", 0)), int(row.get("line_num", 0)),
                    int(row.get("word_num", 0)),
                ))
            text = _words_to_text(words)
            average = sum(word.confidence for word in words) / len(words) if words else 0.0
            return OCRResult(OCRStatus.SUCCESS, text=text, confidence=average, words=tuple(words))
        except (OSError, subprocess.SubprocessError, csv.Error, KeyError, ValueError) as exc:
            return OCRResult(OCRStatus.FAILED, reason=f"로컬 Tesseract 실행 실패: {exc}")
        finally:
            if temporary:
                Path(temporary).unlink(missing_ok=True)


def _words_to_text(words: list[OCRWord]) -> str:
    lines: dict[tuple[int, int], list[OCRWord]] = {}
    for word in words:
        lines.setdefault((word.block_no, word.line_no), []).append(word)
    return "\n".join(
        " ".join(word.text for word in sorted(line, key=lambda item: item.bbox[0]))
        for _, line in sorted(lines.items())
    )
