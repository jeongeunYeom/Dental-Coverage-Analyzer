from dental_coverage_analyzer.core.resources import load_config


def test_packaged_configs_are_available_without_checkout_paths(monkeypatch):
    import dental_coverage_analyzer.core.resources as resource_module
    monkeypatch.setattr(resource_module, "project_root", lambda: resource_module.Path("/missing"))
    assert "include" in load_config("dental_keywords.json")
    assert "MERITZ" in load_config("provider_patterns.json")
    assert load_config("ocr_settings.json")["minimum_confidence"] == 65.0
