"""Tests for load configuration model serialization."""

from __future__ import annotations

from custom_components.peakshavr.const import (
    CONF_LOAD_COOLDOWN_S,
    CONF_LOAD_ENTITY_ID,
    CONF_LOAD_MANUAL_EXPECTED_KW,
    CONF_LOAD_MIN_ON_TIME_S,
    CONF_LOAD_MIN_REQUIRED_KW,
    CONF_LOAD_POWER_SENSOR,
    CONF_LOAD_PRIORITY,
)
from custom_components.peakshavr.models import LoadConfig


def test_load_config_roundtrip_includes_min_required_kw() -> None:
    raw = {
        CONF_LOAD_ENTITY_ID: "switch.boiler",
        CONF_LOAD_PRIORITY: 10,
        CONF_LOAD_COOLDOWN_S: 120,
        CONF_LOAD_MIN_ON_TIME_S: 90,
        CONF_LOAD_POWER_SENSOR: "sensor.boiler_power",
        CONF_LOAD_MANUAL_EXPECTED_KW: 1.8,
        CONF_LOAD_MIN_REQUIRED_KW: 0.7,
    }
    load = LoadConfig.from_mapping(raw)
    assert load.min_required_kw == 0.7
    assert load.as_mapping()[CONF_LOAD_MIN_REQUIRED_KW] == 0.7


def test_load_config_defaults_to_none_min_required_kw() -> None:
    load = LoadConfig.from_mapping(
        {
            CONF_LOAD_ENTITY_ID: "switch.pump",
            CONF_LOAD_PRIORITY: 1,
        }
    )
    assert load.min_required_kw is None
