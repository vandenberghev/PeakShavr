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
from .entity_helpers import load_device_info, load_key


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up PeakShavr binary sensors."""
    coordinator: PeakShavrCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[BinarySensorEntity] = [
        PeakShavrEscalationBinarySensor(coordinator, entry),
        PeakShavrDegradedBinarySensor(coordinator, entry),
    ]
    entities.extend(
        PeakShavrLoadShedBinarySensor(coordinator, entry, load.entity_id)
        for load in coordinator.load_configs
    )
    async_add_entities(entities)


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


class PeakShavrLoadShedBinarySensor(
    CoordinatorEntity[PeakShavrCoordinator], BinarySensorEntity
):
    """Diagnostic sensor indicating whether a load is currently shed."""

    _attr_has_entity_name = True
    _attr_name = "Shed by PeakShavr"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: PeakShavrCoordinator,
        entry: ConfigEntry,
        load_entity_id: str,
    ) -> None:
        super().__init__(coordinator)
        self._load_entity_id = load_entity_id
        self._attr_unique_id = f"{entry.entry_id}_{load_key(load_entity_id)}_shed"
        self._attr_device_info = load_device_info(coordinator, entry, load_entity_id)

    @property
    def is_on(self) -> bool:
        return self.coordinator.is_load_shed(self._load_entity_id)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "managed_entity_id": self._load_entity_id,
            "external_override": self.coordinator.is_load_external_override(
                self._load_entity_id
            ),
            "blocked_by_min_required_draw": self.coordinator.load_blocked_by_threshold(
                self._load_entity_id
            ),
        }
