from pathlib import Path
import json

from scripts.check_no_tracked_binaries import tracked_binary_paths


ROOT = Path(__file__).parents[1]


def test_pyinstaller_spec_is_onedir_and_bundles_resources():
    spec = (ROOT / "DentalCoverageAnalyzer.spec").read_text(encoding="utf-8")
    assert 'name="DentalCoverageAnalyzer"' in spec
    assert "COLLECT(" in spec
    assert "exclude_binaries=True" in spec
    assert "dental_coverage_analyzer/resources" in spec
    assert "PySide6.QtPrintSupport" in spec
    assert 'icon = root / "build" / "generated" / "app_icon.ico"' in spec
    assert 'icon=str(icon)' in spec
    assert 'version=str(root / "packaging" / "version_info.txt")' in spec
    assert 'datas.append((str(tesseract), "tesseract"))' in spec
    assert 'contents_directory="."' in spec


def test_windows_build_script_and_workflow_publish_expected_artifact():
    batch = (ROOT / "build_exe.bat").read_text(encoding="utf-8")
    workflow = (ROOT / ".github/workflows/build-windows.yml").read_text(encoding="utf-8")
    assert "DentalCoverageAnalyzer.spec" in batch
    assert "dist\\DentalCoverageAnalyzer\\DentalCoverageAnalyzer.exe" in batch
    assert "windows-latest" in workflow
    assert 'python-version: "3.11"' in workflow
    assert "prepare_tesseract_windows.ps1" in workflow
    assert "python scripts/build_icon.py" in workflow
    assert "DentalCoverageAnalyzer-Windows-Portable" in workflow
    assert "DentalCoverageAnalyzer-Windows-Installer" in workflow
    assert "Inno Setup" in workflow
    assert "Using preinstalled Inno Setup" in workflow
    assert "choco install innosetup --version=6.7.1" in workflow
    assert '"ISCC_PATH=$iscc"' in workflow
    assert '& "$env:ISCC_PATH"' in workflow
    assert "--health-check" in workflow
    assert "upload-artifact@v4" in workflow


def test_installer_metadata_and_ocr_bundle_contracts_exist():
    installer = (ROOT / "installer/DentalCoverageAnalyzer.iss").read_text(encoding="utf-8")
    preparation = (ROOT / "scripts/prepare_tesseract_windows.ps1").read_text(encoding="utf-8")
    manifest = json.loads((ROOT / "packaging/tesseract_manifest.json").read_text(encoding="utf-8"))
    metadata = (ROOT / "packaging/version_info.txt").read_text(encoding="utf-8")
    assert "7A834503-7785-43DF-90E1-9BC6600601A8" in installer
    assert "desktopicon" in installer
    assert "UninstallDisplayIcon" in installer
    assert "recursesubdirs" in installer
    assert manifest["windows_binary"]["version"] == "5.3.3.20231005"
    assert manifest["windows_binary"]["download_url"].startswith("https://")
    assert manifest["windows_binary"]["sha256"]
    assert manifest["traineddata"]["eng"]["sha256"]
    assert manifest["traineddata"]["kor"]["sha256"]
    assert "tesseract_manifest.json" in preparation
    assert "--require-checksums" in preparation
    assert "kor.traineddata" in preparation and "eng.traineddata" in preparation
    assert "FileDescription" in metadata and "ProductVersion" in metadata
    assert (ROOT / "assets/app_icon.svg").read_text(encoding="utf-8").startswith("<?xml")
    assert (ROOT / "scripts/build_icon.py").is_file()
    assert "build\\generated\\app_icon.ico" in installer


def test_repository_tracks_no_release_binaries():
    assert tracked_binary_paths(ROOT) == []
