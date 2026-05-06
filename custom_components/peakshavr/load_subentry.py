"""Helpers for load subentry metadata and expected-source mode handling."""

from __future__ import annotations

import re

from .const import (
    LOAD_EXPECTED_SOURCE_MANUAL,
    LOAD_EXPECTED_SOURCE_SENSOR,
    LOAD_SUBENTRY_PRIORITY_WIDTH,
)

_TITLE_PREFIX_RE = re.compile(r"^\[P\d+\]\s*")


def infer_expected_source_mode(
    stored_mode: object | None,
    *,
    power_sensor: str | None,
    manual_expected_kw: float | None,
) -> str:
    """Resolve expected-source mode with backward-compatible inference."""
    if stored_mode == LOAD_EXPECTED_SOURCE_MANUAL:
        return LOAD_EXPECTED_SOURCE_MANUAL
    if stored_mode == LOAD_EXPECTED_SOURCE_SENSOR:
        return LOAD_EXPECTED_SOURCE_SENSOR
    if manual_expected_kw is not None and power_sensor is None:
        return LOAD_EXPECTED_SOURCE_MANUAL
    return LOAD_EXPECTED_SOURCE_SENSOR


def format_load_subentry_title(priority: int, display_name: str) -> str:
    """Build a sortable subentry title that still shows priority."""
    safe_name = (display_name or "").strip()
    if not safe_name:
        safe_name = "Load"
    return f"[P{priority:0{LOAD_SUBENTRY_PRIORITY_WIDTH}d}] {safe_name}"


def load_display_name_from_title(title: str | None, fallback: str) -> str:
    """Extract display name from a title that may already include a priority prefix."""
    if title:
        normalized = _TITLE_PREFIX_RE.sub("", title).strip()
        if normalized:
            return normalized
    return fallback
