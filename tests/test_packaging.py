from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_pyinstaller_spec_is_onedir_and_bundles_resources():
    spec = (ROOT / "DentalCoverageAnalyzer.spec").read_text(encoding="utf-8")
    assert 'name="DentalCoverageAnalyzer"' in spec
    assert "COLLECT(" in spec
    assert "exclude_binaries=True" in spec
    assert "dental_coverage_analyzer/resources" in spec
    assert "PySide6.QtPrintSupport" in spec


def test_windows_build_script_and_workflow_publish_expected_artifact():
    batch = (ROOT / "build_exe.bat").read_text(encoding="utf-8")
    workflow = (ROOT / ".github/workflows/build-windows.yml").read_text(encoding="utf-8")
    assert "DentalCoverageAnalyzer.spec" in batch
    assert "dist\\DentalCoverageAnalyzer\\DentalCoverageAnalyzer.exe" in batch
    assert "windows-latest" in workflow
    assert 'python-version: "3.11"' in workflow
    assert "DentalCoverageAnalyzer-Windows" in workflow
    assert "upload-artifact@v4" in workflow
