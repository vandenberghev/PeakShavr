"""Runtime configuration helpers for PeakShavr."""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import replace
from collections.abc import Mapping

from homeassistant.config_entries import ConfigEntry

from .const import (
    CONF_ENABLED,
    CONF_ENERGY_MODE,
    CONF_ENERGY_SENSOR,
    CONF_ENERGY_SENSOR_DAY,
    CONF_ENERGY_SENSOR_NIGHT,
    CONF_ESCALATION_INTERVAL_SECONDS,
    CONF_ESCALATION_WINDOW_SECONDS,
    CONF_LOADS,
    CONF_NORMAL_INTERVAL_SECONDS,
    CONF_OVERRIDE_BACKOFF_SECONDS,
    CONF_POWER_SENSOR,
    CONF_TARGET_KW,
    CONF_TELEMETRY_CONFLICT_ABS_KW,
    CONF_TELEMETRY_CONFLICT_REL,
    CONF_TELEMETRY_SILENCE_SECONDS,
    DEFAULT_ESCALATION_INTERVAL_SECONDS,
    DEFAULT_ESCALATION_WINDOW_SECONDS,
    DEFAULT_NORMAL_INTERVAL_SECONDS,
    DEFAULT_OVERRIDE_BACKOFF_SECONDS,
    DEFAULT_TARGET_KW,
    DEFAULT_TELEMETRY_CONFLICT_ABS_KW,
    DEFAULT_TELEMETRY_CONFLICT_REL,
    DEFAULT_TELEMETRY_SILENCE_SECONDS,
    ENERGY_MODE_TOTAL,
    SUBENTRY_TYPE_LOAD,
)
from .models import LoadConfig


@dataclass(slots=True, frozen=True)
class RuntimeConfig:
    """Resolved runtime configuration."""

    power_sensor: str
    energy_mode: str
    energy_sensor: str | None
    energy_sensor_day: str | None
    energy_sensor_night: str | None
    target_kw: float
    telemetry_silence_seconds: int
    telemetry_conflict_abs_kw: float
    telemetry_conflict_rel: float
    override_backoff_seconds: int
    normal_interval_seconds: int
    escalation_interval_seconds: int
    escalation_window_seconds: int
    enabled: bool
    loads: tuple[LoadConfig, ...]

    @property
    def energy_entity_ids(self) -> tuple[str, ...]:
        """All energy entities this config depends on."""
        if self.energy_mode == ENERGY_MODE_TOTAL:
            return (self.energy_sensor,) if self.energy_sensor else ()
        if self.energy_sensor_day and self.energy_sensor_night:
            return (self.energy_sensor_day, self.energy_sensor_night)
        return ()


def resolve_runtime_config(entry: ConfigEntry) -> RuntimeConfig:
    """Resolve merged config from data and options."""
    merged: dict[str, object] = {**entry.data, **entry.options}
    loads = _resolve_loads(entry, merged)

    return RuntimeConfig(
        power_sensor=str(merged[CONF_POWER_SENSOR]),
        energy_mode=str(merged.get(CONF_ENERGY_MODE, ENERGY_MODE_TOTAL)),
        energy_sensor=_as_optional_str(merged.get(CONF_ENERGY_SENSOR)),
        energy_sensor_day=_as_optional_str(merged.get(CONF_ENERGY_SENSOR_DAY)),
        energy_sensor_night=_as_optional_str(merged.get(CONF_ENERGY_SENSOR_NIGHT)),
        target_kw=float(merged.get(CONF_TARGET_KW, DEFAULT_TARGET_KW)),
        telemetry_silence_seconds=int(
            merged.get(CONF_TELEMETRY_SILENCE_SECONDS, DEFAULT_TELEMETRY_SILENCE_SECONDS)
        ),
        telemetry_conflict_abs_kw=float(
            merged.get(CONF_TELEMETRY_CONFLICT_ABS_KW, DEFAULT_TELEMETRY_CONFLICT_ABS_KW)
        ),
        telemetry_conflict_rel=float(
            merged.get(CONF_TELEMETRY_CONFLICT_REL, DEFAULT_TELEMETRY_CONFLICT_REL)
        ),
        override_backoff_seconds=int(
            merged.get(CONF_OVERRIDE_BACKOFF_SECONDS, DEFAULT_OVERRIDE_BACKOFF_SECONDS)
        ),
        normal_interval_seconds=int(
            merged.get(CONF_NORMAL_INTERVAL_SECONDS, DEFAULT_NORMAL_INTERVAL_SECONDS)
        ),
        escalation_interval_seconds=int(
            merged.get(
                CONF_ESCALATION_INTERVAL_SECONDS, DEFAULT_ESCALATION_INTERVAL_SECONDS
            )
        ),
        escalation_window_seconds=int(
            merged.get(CONF_ESCALATION_WINDOW_SECONDS, DEFAULT_ESCALATION_WINDOW_SECONDS)
        ),
        enabled=bool(merged.get(CONF_ENABLED, True)),
        loads=loads,
    )


def _resolve_loads(entry: ConfigEntry, merged: Mapping[str, object]) -> tuple[LoadConfig, ...]:
    subentry_loads: list[LoadConfig] = []
    for subentry in entry.subentries.values():
        if subentry.subentry_type != SUBENTRY_TYPE_LOAD:
            continue
        subentry_loads.append(
            replace(
                LoadConfig.from_mapping(dict(subentry.data)),
                config_subentry_id=subentry.subentry_id,
            )
        )

    if subentry_loads:
        return tuple(sorted(subentry_loads, key=lambda load: (load.priority, load.entity_id)))

    option_loads = tuple(
        LoadConfig.from_mapping(dict(load_data))
        for load_data in merged.get(CONF_LOADS, [])
        if isinstance(load_data, Mapping)
    )
    return tuple(sorted(option_loads, key=lambda load: (load.priority, load.entity_id)))


def _as_optional_str(value: object | None) -> str | None:
    if value is None:
        return None
    value_as_str = str(value).strip()
    return value_as_str if value_as_str else None
