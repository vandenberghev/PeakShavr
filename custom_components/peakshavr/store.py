"""Persistent storage for PeakShavr runtime state."""

from __future__ import annotations

from typing import TypedDict

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN, STORAGE_VERSION


class PersistedState(TypedDict, total=False):
    """Persisted runtime state."""

    quarter_start: str
    energy_at_quarter_start_kwh: float
    shed_stack: list[str]
    last_shed_at: dict[str, float]
    last_restore_at: dict[str, float]
    override_backoff_until: dict[str, float]
    load_samples: dict[str, list[float]]
    monthly_peak_kw: float
    monthly_peak_timestamp: float | None
    month_key: str
    uncertain_quarter: bool
    enabled: bool
    last_action: str
    degraded_reason: str | None
    external_overrides: list[str]
    power_last_reported_ts: float | None
    power_last_reported_kw: float | None


class PeakShavrStore:
    """Storage wrapper around Home Assistant Store helper."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self._store = Store[PersistedState](
            hass,
            STORAGE_VERSION,
            f"{DOMAIN}.{entry_id}",
        )

    async def async_load(self) -> PersistedState | None:
        """Load persisted state."""
        return await self._store.async_load()

    async def async_save(self, payload: PersistedState) -> None:
        """Persist runtime state."""
        await self._store.async_save(payload)

