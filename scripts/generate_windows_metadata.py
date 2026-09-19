from __future__ import annotations

from pathlib import Path
import tomllib


ROOT = Path(__file__).parents[1]
version = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
parts = [int(part) for part in version.split(".")]
quad = tuple((parts + [0, 0, 0, 0])[:4])
(ROOT / "packaging").mkdir(exist_ok=True)
(ROOT / "packaging/version_info.txt").write_text(f'''# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(filevers={quad}, prodvers={quad}, mask=0x3f, flags=0x0,
    OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[StringFileInfo([StringTable('041204B0', [
    StringStruct('FileDescription', '치아보험 보장분석표 생성기'),
    StringStruct('CompanyName', 'Independent Software Publisher'),
    StringStruct('FileVersion', '{version}'),
    StringStruct('InternalName', 'DentalCoverageAnalyzer'),
    StringStruct('OriginalFilename', 'DentalCoverageAnalyzer.exe'),
    StringStruct('ProductName', 'Dental Coverage Analyzer'),
    StringStruct('ProductVersion', '{version}'),
    StringStruct('LegalCopyright', 'Copyright (c) 2026. All rights reserved.')
  ])]), VarFileInfo([VarStruct('Translation', [1042, 1200])])]
)
''', encoding="utf-8")
(ROOT / "packaging/version.iss").write_text(f'#define AppVersion "{version}"\n', encoding="utf-8")
print(version)
