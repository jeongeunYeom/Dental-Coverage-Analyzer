import pytest

from dental_coverage_analyzer.core.money import parse_money


@pytest.mark.parametrize(("raw", "expected"), [
    ("50만원", 500_000),
    ("0.5만", 5_000),
    ("200만원", 2_000_000),
    ("1억", 100_000_000),
    ("1억5,000만", 150_000_000),
    ("17,610원", 17_610),
    ("1억 5,000만원", 150_000_000),
    ("0원", 0),
])
def test_parse_korean_money(raw, expected):
    result = parse_money(raw)
    assert result is not None
    assert result.value == expected
    assert result.raw == raw


@pytest.mark.parametrize("raw", [None, "", "50000", "정보 없음", "1.234원"])
def test_rejects_unconfirmed_or_fractional_won(raw):
    assert parse_money(raw) is None
