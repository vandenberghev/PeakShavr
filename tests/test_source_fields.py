"""Tests for source-field requirement and normalization helpers."""

from __future__ import annotations

from custom_components.peakshavr.const import (
    CONF_ENERGY_MODE,
    CONF_ENERGY_SENSOR,
    CONF_ENERGY_SENSOR_DAY,
    CONF_ENERGY_SENSOR_NIGHT,
    CONF_POWER_SENSOR,
    ENERGY_MODE_SPLIT,
    ENERGY_MODE_TOTAL,
)
from custom_components.peakshavr.source_fields import (
    normalize_source_fields,
    source_field_requirements,
)


def test_source_field_requirements_initial_form_has_no_required_energy_field() -> None:
    assert source_field_requirements(None) == (False, False, False)


def test_source_field_requirements_total_mode() -> None:
    assert source_field_requirements({CONF_ENERGY_MODE: ENERGY_MODE_TOTAL}) == (
        True,
        False,
        False,
    )


def test_source_field_requirements_split_mode() -> None:
    assert source_field_requirements({CONF_ENERGY_MODE: ENERGY_MODE_SPLIT}) == (
        False,
        True,
        True,
    )


def test_normalize_source_fields_total_mode_clears_split_fields() -> None:
    normalized = normalize_source_fields(
        {
            CONF_POWER_SENSOR: "sensor.grid_power",
            CONF_ENERGY_MODE: ENERGY_MODE_TOTAL,
            CONF_ENERGY_SENSOR: "sensor.energy_total",
            CONF_ENERGY_SENSOR_DAY: "sensor.energy_day",
            CONF_ENERGY_SENSOR_NIGHT: "sensor.energy_night",
        }
    )
    assert normalized[CONF_ENERGY_SENSOR] == "sensor.energy_total"
    assert normalized[CONF_ENERGY_SENSOR_DAY] is None
    assert normalized[CONF_ENERGY_SENSOR_NIGHT] is None


def test_normalize_source_fields_split_mode_clears_total_field() -> None:
    normalized = normalize_source_fields(
        {
            CONF_POWER_SENSOR: "sensor.grid_power",
            CONF_ENERGY_MODE: ENERGY_MODE_SPLIT,
            CONF_ENERGY_SENSOR: "sensor.energy_total",
            CONF_ENERGY_SENSOR_DAY: "sensor.energy_day",
            CONF_ENERGY_SENSOR_NIGHT: "sensor.energy_night",
        }
    )
    assert normalized[CONF_ENERGY_SENSOR] is None
    assert normalized[CONF_ENERGY_SENSOR_DAY] == "sensor.energy_day"
    assert normalized[CONF_ENERGY_SENSOR_NIGHT] == "sensor.energy_night"
