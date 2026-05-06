"""Constants for PeakShavr."""

from __future__ import annotations

from enum import StrEnum

try:
    from homeassistant.components.input_boolean import DOMAIN as INPUT_BOOLEAN_DOMAIN
    from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
    from homeassistant.const import Platform
except ImportError:  # pragma: no cover - local unit tests without Home Assistant
    INPUT_BOOLEAN_DOMAIN = "input_boolean"
    SWITCH_DOMAIN = "switch"

    class Platform(StrEnum):
        BINARY_SENSOR = "binary_sensor"
        SENSOR = "sensor"
        SWITCH = "switch"


DOMAIN = "peakshavr"
NAME = "PeakShavr"

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
    Platform.SWITCH,
]

CONF_POWER_SENSOR = "power_sensor"
CONF_ENERGY_MODE = "energy_mode"
CONF_ENERGY_SENSOR = "energy_sensor"
CONF_ENERGY_SENSOR_DAY = "energy_sensor_day"
CONF_ENERGY_SENSOR_NIGHT = "energy_sensor_night"
CONF_TARGET_KW = "target_kw"

CONF_LOADS = "loads"
CONF_LOAD_ENTITY_ID = "entity_id"
CONF_LOAD_PRIORITY = "priority"
CONF_LOAD_POWER_SENSOR = "power_sensor"
CONF_LOAD_MANUAL_EXPECTED_KW = "manual_expected_kw"
CONF_LOAD_MIN_REQUIRED_KW = "min_required_kw"
CONF_LOAD_COOLDOWN_S = "cooldown_seconds"
CONF_LOAD_MIN_ON_TIME_S = "min_on_time_seconds"

CONF_TELEMETRY_SILENCE_SECONDS = "telemetry_silence_seconds"
CONF_TELEMETRY_CONFLICT_ABS_KW = "telemetry_conflict_abs_kw"
CONF_TELEMETRY_CONFLICT_REL = "telemetry_conflict_rel"
CONF_OVERRIDE_BACKOFF_SECONDS = "override_backoff_seconds"
CONF_NORMAL_INTERVAL_SECONDS = "normal_interval_seconds"
CONF_ESCALATION_INTERVAL_SECONDS = "escalation_interval_seconds"
CONF_ESCALATION_WINDOW_SECONDS = "escalation_window_seconds"
CONF_ENABLED = "enabled"

ENERGY_MODE_TOTAL = "total"
ENERGY_MODE_SPLIT = "split"

LOAD_SUPPORTED_DOMAINS: tuple[str, ...] = (SWITCH_DOMAIN, INPUT_BOOLEAN_DOMAIN)

DEFAULT_TARGET_KW = 3.0
DEFAULT_LOAD_COOLDOWN_SECONDS = 60
DEFAULT_LOAD_MIN_ON_TIME_SECONDS = 60
DEFAULT_TELEMETRY_SILENCE_SECONDS = 120
DEFAULT_TELEMETRY_CONFLICT_ABS_KW = 0.2
DEFAULT_TELEMETRY_CONFLICT_REL = 0.15
DEFAULT_OVERRIDE_BACKOFF_SECONDS = 300
DEFAULT_NORMAL_INTERVAL_SECONDS = 30
DEFAULT_ESCALATION_INTERVAL_SECONDS = 10
DEFAULT_ESCALATION_WINDOW_SECONDS = 120
DEFAULT_LOAD_EXPECTED_KW = 0.5
SUBENTRY_TYPE_LOAD = "load"

STORAGE_VERSION = 1
STORAGE_KEY = DOMAIN

ATTR_DEGRADED_REASON = "degraded_reason"
ATTR_UNCERTAIN_QUARTER = "uncertain_quarter"

# Maximum plausible energy consumed in a single 15-minute quarter (kWh).
# Used to detect suspicious forward meter jumps.  100 kW × 0.25 h = 25 kWh.
MAX_PLAUSIBLE_QUARTER_KWH = 25.0
