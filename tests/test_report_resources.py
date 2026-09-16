from dental_coverage_analyzer.core.resources import load_text_resource


def test_report_resources_are_packaged():
    assert "{{AGGREGATE_CARDS}}" in load_text_resource("report/template.html")
    assert "@page" in load_text_resource("report/report.css")
