"""Numeric parsing helpers for user-entered form values."""

from __future__ import annotations


def parse_localized_float(value: object) -> float | None:
    """Parse a float from text, accepting both comma and dot separators."""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    if not isinstance(value, str):
        return None

    normalized = value.strip().replace(",", ".")
    if not normalized:
        return None

    try:
        return float(normalized)
    except ValueError:
        return None


def format_optional_kw(value: float | None) -> str | None:
    """Format optional kW value for suggested form values."""
    if value is None:
        return None
    return f"{value:g}"
