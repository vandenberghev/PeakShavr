"""Data models for PeakShavr."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .const import (
    CONF_LOAD_COOLDOWN_S,
    CONF_LOAD_ENTITY_ID,
    CONF_LOAD_MANUAL_EXPECTED_KW,
    CONF_LOAD_MIN_REQUIRED_KW,
    CONF_LOAD_MIN_ON_TIME_S,
    CONF_LOAD_POWER_SENSOR,
    CONF_LOAD_PRIORITY,
    DEFAULT_LOAD_COOLDOWN_SECONDS,
    DEFAULT_LOAD_MIN_ON_TIME_SECONDS,
)


@dataclass(slots=True, frozen=True)
class LoadConfig:
    """Configuration of one managed load."""

    entity_id: str
    priority: int
    cooldown_seconds: int = DEFAULT_LOAD_COOLDOWN_SECONDS
    min_on_time_seconds: int = DEFAULT_LOAD_MIN_ON_TIME_SECONDS
    power_sensor: str | None = None
    manual_expected_kw: float | None = None
    min_required_kw: float | None = None
    config_subentry_id: str | None = None

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "LoadConfig":
        """Create a load configuration from a persisted mapping."""
        return cls(
            entity_id=data[CONF_LOAD_ENTITY_ID],
            priority=int(data.get(CONF_LOAD_PRIORITY, 0)),
            cooldown_seconds=int(
                data.get(CONF_LOAD_COOLDOWN_S, DEFAULT_LOAD_COOLDOWN_SECONDS)
            ),
            min_on_time_seconds=int(
                data.get(CONF_LOAD_MIN_ON_TIME_S, DEFAULT_LOAD_MIN_ON_TIME_SECONDS)
            ),
            power_sensor=data.get(CONF_LOAD_POWER_SENSOR),
            manual_expected_kw=(
                float(data[CONF_LOAD_MANUAL_EXPECTED_KW])
                if data.get(CONF_LOAD_MANUAL_EXPECTED_KW) is not None
                else None
            ),
            min_required_kw=(
                float(data[CONF_LOAD_MIN_REQUIRED_KW])
                if data.get(CONF_LOAD_MIN_REQUIRED_KW) is not None
                else None
            ),
        )

    def as_mapping(self) -> dict[str, Any]:
        """Serialize to config-entry options."""
        return {
            CONF_LOAD_ENTITY_ID: self.entity_id,
            CONF_LOAD_PRIORITY: self.priority,
            CONF_LOAD_COOLDOWN_S: self.cooldown_seconds,
            CONF_LOAD_MIN_ON_TIME_S: self.min_on_time_seconds,
            CONF_LOAD_POWER_SENSOR: self.power_sensor,
            CONF_LOAD_MANUAL_EXPECTED_KW: self.manual_expected_kw,
            CONF_LOAD_MIN_REQUIRED_KW: self.min_required_kw,
        }
