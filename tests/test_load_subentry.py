"""Tests for load subentry helper logic."""

from __future__ import annotations

from custom_components.peakshavr.const import (
    LOAD_EXPECTED_SOURCE_MANUAL,
    LOAD_EXPECTED_SOURCE_SENSOR,
)
from custom_components.peakshavr.load_subentry import (
    format_load_subentry_title,
    infer_expected_source_mode,
    load_display_name_from_title,
)


def test_format_load_subentry_title_includes_sortable_priority_prefix() -> None:
    assert format_load_subentry_title(2, "Boiler") == "[P0002] Boiler"
    assert format_load_subentry_title(10, "Boiler") == "[P0010] Boiler"


def test_load_display_name_from_title_strips_priority_prefix() -> None:
    assert load_display_name_from_title("[P0007] Heat Pump", "switch.hp") == "Heat Pump"
    assert load_display_name_from_title("Heat Pump", "switch.hp") == "Heat Pump"
    assert load_display_name_from_title("", "switch.hp") == "switch.hp"


def test_infer_expected_source_mode_prefers_stored_mode() -> None:
    assert (
        infer_expected_source_mode(
            LOAD_EXPECTED_SOURCE_MANUAL,
            power_sensor="sensor.boiler_power",
            manual_expected_kw=1.5,
        )
        == LOAD_EXPECTED_SOURCE_MANUAL
    )
    assert (
        infer_expected_source_mode(
            LOAD_EXPECTED_SOURCE_SENSOR,
            power_sensor=None,
            manual_expected_kw=1.5,
        )
        == LOAD_EXPECTED_SOURCE_SENSOR
    )


def test_infer_expected_source_mode_backwards_compatible_inference() -> None:
    assert (
        infer_expected_source_mode(
            None,
            power_sensor=None,
            manual_expected_kw=1.5,
        )
        == LOAD_EXPECTED_SOURCE_MANUAL
    )
    assert (
        infer_expected_source_mode(
            None,
            power_sensor="sensor.boiler_power",
            manual_expected_kw=1.5,
        )
        == LOAD_EXPECTED_SOURCE_SENSOR
    )
