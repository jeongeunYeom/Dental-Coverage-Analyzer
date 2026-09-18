from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile

from dental_coverage_analyzer.branding import BrandingSettings, DEFAULT_PRIMARY_COLOR

from .project_store import app_data_dir


SETTINGS_SCHEMA_VERSION = 1


def settings_path() -> Path:
    return app_data_dir() / "settings.json"


def load_settings(path: str | Path | None = None) -> BrandingSettings:
    target = Path(path) if path else settings_path()
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
        if payload.get("schema_version") != SETTINGS_SCHEMA_VERSION:
            return BrandingSettings()
        data = payload.get("branding", {})
        allowed = BrandingSettings.__dataclass_fields__.keys()
        values = {key: data[key] for key in allowed if key in data}
        settings = BrandingSettings(**values)
        if not _valid_color(settings.primary_color):
            settings.primary_color = DEFAULT_PRIMARY_COLOR
        return settings
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return BrandingSettings()


def save_settings(settings: BrandingSettings, path: str | Path | None = None) -> Path:
    target = Path(path) if path else settings_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {"schema_version": SETTINGS_SCHEMA_VERSION, "branding": settings.to_dict()}
    fd, temporary = tempfile.mkstemp(prefix=target.name + ".", suffix=".tmp", dir=target.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.flush(); os.fsync(handle.fileno())
        os.replace(temporary, target)
    except Exception:
        Path(temporary).unlink(missing_ok=True)
        raise
    return target


def copy_brand_logo(source: str | Path, root: str | Path | None = None) -> Path:
    source_path = Path(source)
    suffix = source_path.suffix.lower()
    if suffix not in {".png", ".jpg", ".jpeg"} or not source_path.is_file():
        raise ValueError("이미지 파일을 사용할 수 없습니다.")
    content = source_path.read_bytes()
    is_png = content.startswith(b"\x89PNG\r\n\x1a\n")
    is_jpeg = content.startswith(b"\xff\xd8\xff")
    if not (is_png or is_jpeg):
        raise ValueError("이미지 파일을 사용할 수 없습니다.")
    folder = Path(root) if root else app_data_dir() / "branding"
    folder.mkdir(parents=True, exist_ok=True)
    name = f"logo-{hashlib.sha256(content).hexdigest()[:12]}{suffix}"
    target = folder / name
    if not target.exists():
        temporary = folder / (name + ".tmp")
        shutil.copyfile(source_path, temporary); os.replace(temporary, target)
    return target


def _valid_color(value: str) -> bool:
    return len(value) == 7 and value.startswith("#") and all(c in "0123456789abcdefABCDEF" for c in value[1:])
