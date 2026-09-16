# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules

root = Path(SPECPATH)
src = root / "src"
resources = src / "dental_coverage_analyzer" / "resources"

datas = [
    (str(resources), "dental_coverage_analyzer/resources"),
    (str(root / "config"), "config"),
]
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
    icon=None,
)
coll = COLLECT(
    exe, a.binaries, a.datas,
    strip=False,
    upx=False,
    name="DentalCoverageAnalyzer",
)
