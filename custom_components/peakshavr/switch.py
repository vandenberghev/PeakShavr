"""Switch platform for PeakShavr."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
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
    """Set up PeakShavr switch entities."""
    coordinator: PeakShavrCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SwitchEntity] = [PeakShavrEnabledSwitch(coordinator, entry)]
    entities.extend(
        PeakShavrManagedLoadSwitch(coordinator, entry, load.entity_id)
        for load in coordinator.load_configs
    )
    async_add_entities(entities)


class PeakShavrEnabledSwitch(CoordinatorEntity[PeakShavrCoordinator], SwitchEntity):
    """Enable/disable switch for controller runtime."""

    _attr_has_entity_name = True
    _attr_name = "Enabled"
    _attr_translation_key = "enabled"

    def __init__(self, coordinator: PeakShavrCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_enabled"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": NAME,
            "manufacturer": NAME,
        }

    @property
    def is_on(self) -> bool:
        return self.coordinator.enabled

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_enabled(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_enabled(False)


class PeakShavrManagedLoadSwitch(CoordinatorEntity[PeakShavrCoordinator], SwitchEntity):
    """Proxy control switch for one managed load."""

    _attr_has_entity_name = True
    _attr_name = "Control"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: PeakShavrCoordinator,
        entry: ConfigEntry,
        load_entity_id: str,
    ) -> None:
        super().__init__(coordinator)
        self._load_entity_id = load_entity_id
        self._attr_unique_id = f"{entry.entry_id}_{load_key(load_entity_id)}_load_control"
        self._attr_device_info = load_device_info(coordinator, entry, load_entity_id)

    @property
    def available(self) -> bool:
        return self.coordinator.load_is_available(self._load_entity_id)

    @property
    def is_on(self) -> bool:
        return self.coordinator.load_is_on(self._load_entity_id)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        load = self.coordinator.get_load_config(self._load_entity_id)
        reference_kw = self.coordinator.load_threshold_reference_kw(self._load_entity_id)
        return {
            "managed_entity_id": self._load_entity_id,
            "priority": load.priority if load else None,
            "power_sensor": load.power_sensor if load else None,
            "manual_expected_kw": load.manual_expected_kw if load else None,
            "min_required_kw": load.min_required_kw if load else None,
            "current_draw_kw": self.coordinator.load_live_kw(self._load_entity_id),
            "threshold_reference_kw": reference_kw,
            "shed_by_controller": self.coordinator.is_load_shed(self._load_entity_id),
            "external_override": self.coordinator.is_load_external_override(
                self._load_entity_id
            ),
            "blocked_by_min_required_draw": self.coordinator.load_blocked_by_threshold(
                self._load_entity_id
            ),
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_user_control_load(self._load_entity_id, turn_on=True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_user_control_load(self._load_entity_id, turn_on=False)
