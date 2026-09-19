import json
from pathlib import Path

from dental_coverage_analyzer.branding import BrandingSettings
from dental_coverage_analyzer.ui.settings_store import copy_brand_logo, load_settings, save_settings


def test_settings_defaults_and_round_trip(tmp_path):
    path = tmp_path / "settings.json"
    assert load_settings(path).primary_color == "#625EF5"
    expected = BrandingSettings("가상 컨설팅", "홍길동", "010-1234-5678", "sample@example.com", "", "상담 안내", "#123ABC", True)
    save_settings(expected, path)
    assert load_settings(path) == expected
    assert json.loads(path.read_text(encoding="utf-8"))["schema_version"] == 1


def test_corrupted_settings_falls_back_to_defaults(tmp_path):
    path = tmp_path / "settings.json"; path.write_text("{broken", encoding="utf-8")
    assert load_settings(path) == BrandingSettings()


def test_logo_is_copied_to_managed_folder(tmp_path):
    source = tmp_path / "source.png"
    source.write_bytes(b"\x89PNG\r\n\x1a\n" + b"synthetic-test-data")
    copied = copy_brand_logo(source, tmp_path / "branding")
    source.unlink()
    assert copied.is_file() and copied.read_bytes().startswith(b"\x89PNG")


def test_onboarding_state_is_persisted(tmp_path):
    path = tmp_path / "settings.json"
    settings = BrandingSettings(onboarding_completed=False); save_settings(settings, path)
    assert not load_settings(path).onboarding_completed
    settings.onboarding_completed = True; save_settings(settings, path)
    assert load_settings(path).onboarding_completed
