"""Tests for localized numeric parsing helpers."""

from __future__ import annotations

from custom_components.peakshavr.number_utils import (
    format_optional_kw,
    parse_localized_float,
)


def test_parse_localized_float_accepts_dot_and_comma() -> None:
    assert parse_localized_float("1.5") == 1.5
    assert parse_localized_float("1,5") == 1.5


def test_parse_localized_float_handles_invalid_and_empty() -> None:
    assert parse_localized_float(None) is None
    assert parse_localized_float("") is None
    assert parse_localized_float("abc") is None
    assert parse_localized_float(True) is None


def test_format_optional_kw() -> None:
    assert format_optional_kw(None) is None
    assert format_optional_kw(2.5) == "2.5"
    assert format_optional_kw(2.0) == "2"
