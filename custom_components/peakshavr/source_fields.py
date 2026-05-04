"""Pure helpers for source-field normalization and requirement selection."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .const import (
    CONF_ENERGY_MODE,
    CONF_ENERGY_SENSOR,
    CONF_ENERGY_SENSOR_DAY,
    CONF_ENERGY_SENSOR_NIGHT,
    CONF_POWER_SENSOR,
    ENERGY_MODE_SPLIT,
    ENERGY_MODE_TOTAL,
)


def normalize_source_fields(user_input: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize source fields so only mode-relevant energy sensors are persisted."""
    mode = str(user_input[CONF_ENERGY_MODE])
    normalized: dict[str, Any] = {
        CONF_POWER_SENSOR: user_input[CONF_POWER_SENSOR],
        CONF_ENERGY_MODE: mode,
        CONF_ENERGY_SENSOR: None,
        CONF_ENERGY_SENSOR_DAY: None,
        CONF_ENERGY_SENSOR_NIGHT: None,
    }
    if mode == ENERGY_MODE_TOTAL:
        normalized[CONF_ENERGY_SENSOR] = user_input.get(CONF_ENERGY_SENSOR)
    else:
        normalized[CONF_ENERGY_SENSOR_DAY] = user_input.get(CONF_ENERGY_SENSOR_DAY)
        normalized[CONF_ENERGY_SENSOR_NIGHT] = user_input.get(CONF_ENERGY_SENSOR_NIGHT)
    return normalized


def source_field_requirements(defaults: Mapping[str, Any] | None) -> tuple[bool, bool, bool]:
    """Return requiredness for (energy_sensor, energy_sensor_day, energy_sensor_night)."""
    if not defaults:
        return False, False, False

    selected_mode = str(defaults.get(CONF_ENERGY_MODE, ENERGY_MODE_TOTAL))
    if selected_mode == ENERGY_MODE_TOTAL:
        return True, False, False
    if selected_mode == ENERGY_MODE_SPLIT:
        return False, True, True
    return False, False, False
