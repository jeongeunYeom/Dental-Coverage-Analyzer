# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules

root = Path(SPECPATH)
src = root / "src"
resources = src / "dental_coverage_analyzer" / "resources"
tesseract = root / "build" / "vendor" / "tesseract"
icon = root / "build" / "generated" / "app_icon.ico"

datas = [
    (str(resources), "dental_coverage_analyzer/resources"),
    (str(root / "config"), "config"),
    (str(root / "THIRD_PARTY_NOTICES.txt"), "."),
]
if not (tesseract / "tesseract.exe").is_file():
    raise SystemExit("Bundled Tesseract is missing; run scripts/prepare_tesseract_windows.ps1")
datas.append((str(tesseract), "tesseract"))
if not icon.is_file():
    raise SystemExit("Generated icon is missing; run scripts/build_icon.py")
datas.append((str(icon), "assets"))
hiddenimports = collect_submodules("dental_coverage_analyzer") + [
    "PySide6.QtPrintSupport",
]

a = Analysis(
    [str(src / "dental_coverage_analyzer" / "gui_main.py")],
    pathex=[str(src)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "torch", "paddle", "easyocr"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True,
    name="DentalCoverageAnalyzer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    contents_directory=".",
    icon=str(icon),
    version=str(root / "packaging" / "version_info.txt"),
)
coll = COLLECT(
    exe, a.binaries, a.datas,
    strip=False,
    upx=False,
    name="DentalCoverageAnalyzer",
)
