"""Validation and sensor conversion utilities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from homeassistant.components.sensor import SensorStateClass
from homeassistant.const import (
    ATTR_STATE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfEnergy,
    UnitOfPower,
)
from homeassistant.core import State

VALID_POWER_UNITS: Final = {
    UnitOfPower.WATT,
    UnitOfPower.KILO_WATT,
}
VALID_ENERGY_UNITS: Final = {
    UnitOfEnergy.WATT_HOUR,
    UnitOfEnergy.KILO_WATT_HOUR,
    UnitOfEnergy.MEGA_WATT_HOUR,
}


@dataclass(slots=True, frozen=True)
class ValidationResult:
    """Validation status for a selected entity."""

    ok: bool
    error_key: str | None = None


def is_state_available(state: State | None) -> bool:
    """Return True when state has a usable value."""
    return bool(
        state
        and state.state not in {STATE_UNKNOWN, STATE_UNAVAILABLE, "", "none", "None"}
    )


def parse_float_state(state: State | None) -> float | None:
    """Parse a state as float if available."""
    if not is_state_available(state):
        return None
    try:
        return float(state.state)
    except ValueError:
        return None


def power_state_to_kw(state: State | None) -> float | None:
    """Convert power state into kW."""
    value = parse_float_state(state)
    if value is None:
        return None

    unit = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) if state else None
    if unit in (UnitOfPower.WATT, "W"):
        return value / 1000
    if unit in (UnitOfPower.KILO_WATT, "kW"):
        return value
    return None


def energy_state_to_kwh(state: State | None) -> float | None:
    """Convert energy state into kWh."""
    value = parse_float_state(state)
    if value is None:
        return None

    unit = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) if state else None
    if unit in (UnitOfEnergy.KILO_WATT_HOUR, "kWh"):
        return value
    if unit in (UnitOfEnergy.WATT_HOUR, "Wh"):
        return value / 1000
    if unit in (UnitOfEnergy.MEGA_WATT_HOUR, "MWh"):
        return value * 1000
    return None


def validate_power_entity_state(state: State | None) -> ValidationResult:
    """Validate selected power sensor."""
    if not is_state_available(state):
        return ValidationResult(False, "power_unavailable")

    unit = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
    if unit not in VALID_POWER_UNITS:
        return ValidationResult(False, "power_unit_invalid")

    if power_state_to_kw(state) is None:
        return ValidationResult(False, "power_non_numeric")

    return ValidationResult(True)


def validate_energy_entity_state(state: State | None) -> ValidationResult:
    """Validate selected energy sensor."""
    if not is_state_available(state):
        return ValidationResult(False, "energy_unavailable")

    unit = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
    if unit not in VALID_ENERGY_UNITS:
        return ValidationResult(False, "energy_unit_invalid")

    state_class = state.attributes.get(ATTR_STATE_CLASS)
    if state_class not in (
        SensorStateClass.TOTAL,
        SensorStateClass.TOTAL_INCREASING,
    ):
        return ValidationResult(False, "energy_state_class_invalid")

    if energy_state_to_kwh(state) is None:
        return ValidationResult(False, "energy_non_numeric")

    return ValidationResult(True)
