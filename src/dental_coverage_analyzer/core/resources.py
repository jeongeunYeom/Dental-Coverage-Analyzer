from pathlib import Path


def project_root() -> Path:
    """소스 checkout의 루트를 반환한다 (패키징 단계에서는 교체 가능)."""
    return Path(__file__).resolve().parents[3]


def config_path(name: str) -> Path:
    return project_root() / "config" / name
