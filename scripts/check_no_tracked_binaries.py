from __future__ import annotations

from pathlib import Path
import subprocess


FORBIDDEN = {".exe", ".dll", ".ico", ".png", ".jpg", ".jpeg", ".traineddata", ".zip", ".msi"}


def tracked_binary_paths(root: Path) -> list[str]:
    output = subprocess.run(
        ["git", "ls-files", "-z"], cwd=root, capture_output=True, check=True,
    ).stdout.decode("utf-8", errors="surrogateescape")
    return sorted(path for path in output.split("\0") if path and Path(path).suffix.casefold() in FORBIDDEN)


def main() -> int:
    paths = tracked_binary_paths(Path(__file__).parents[1])
    if paths:
        print("Git에서 추적하면 안 되는 binary 파일:")
        print("\n".join(f"- {path}" for path in paths))
        return 1
    print("No tracked release binaries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
