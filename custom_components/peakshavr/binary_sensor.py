"""Binary sensor platform for PeakShavr."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, NAME
from .coordinator import PeakShavrCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up PeakShavr binary sensors."""
    coordinator: PeakShavrCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        PeakShavrEscalationBinarySensor(coordinator, entry),
        PeakShavrDegradedBinarySensor(coordinator, entry),
    ])


class PeakShavrEscalationBinarySensor(
    CoordinatorEntity[PeakShavrCoordinator], BinarySensorEntity
):
    """Binary sensor reporting escalation mode."""

    _attr_has_entity_name = True
    _attr_name = "Escalation"
    _attr_translation_key = "escalation"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: PeakShavrCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_escalation"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": NAME,
            "manufacturer": NAME,
        }

    @property
    def is_on(self) -> bool:
        return self.coordinator.escalation_active

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self.coordinator.extra_state_attributes()


class PeakShavrDegradedBinarySensor(
    CoordinatorEntity[PeakShavrCoordinator], BinarySensorEntity
):
    """Binary sensor reporting degraded (low-confidence telemetry) mode."""

    _attr_has_entity_name = True
    _attr_name = "Degraded"
    _attr_translation_key = "degraded"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: PeakShavrCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_degraded"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": NAME,
            "manufacturer": NAME,
        }

    @property
    def is_on(self) -> bool:
        return self.coordinator.degraded_reason is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"reason": self.coordinator.degraded_reason}

