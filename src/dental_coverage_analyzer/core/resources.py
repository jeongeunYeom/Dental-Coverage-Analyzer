from __future__ import annotations

from contextlib import contextmanager
from importlib import resources
import json
from pathlib import Path
import sys
from typing import Any, Iterator


_PACKAGE = "dental_coverage_analyzer.resources.config"


def project_root() -> Path:
    """개발 checkout 또는 frozen application의 resource root를 반환한다."""
    frozen = getattr(sys, "_MEIPASS", None)
    if frozen:
        return Path(frozen)
    return Path(__file__).resolve().parents[3]


def config_path(name: str) -> Path:
    """호환용 filesystem 경로. 새 코드는 load_config를 사용한다."""
    frozen_path = project_root() / "config" / name
    if frozen_path.is_file():
        return frozen_path
    packaged = Path(__file__).resolve().parents[1] / "resources" / "config" / name
    if packaged.is_file():
        return packaged
    return frozen_path


def load_config(name: str) -> dict[str, Any]:
    """source/frozen config를 우선하고 없으면 package data JSON을 읽는다."""
    external = project_root() / "config" / name
    if external.is_file():
        with external.open(encoding="utf-8") as stream:
            return json.load(stream)
    try:
        resource = resources.files(_PACKAGE).joinpath(name)
        return json.loads(resource.read_text(encoding="utf-8"))
    except (FileNotFoundError, ModuleNotFoundError):
        path = config_path(name)
        with path.open(encoding="utf-8") as stream:
            return json.load(stream)


@contextmanager
def bundled_resource(name: str) -> Iterator[Path | None]:
    """선택적 binary resource를 실행 가능한 실제 경로로 노출한다."""
    try:
        resource = resources.files("dental_coverage_analyzer.resources").joinpath(name)
        if not resource.is_file():
            yield None
            return
        with resources.as_file(resource) as path:
            yield path
    except (FileNotFoundError, ModuleNotFoundError):
        yield None
