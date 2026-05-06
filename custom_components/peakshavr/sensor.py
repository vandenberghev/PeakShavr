"""Sensor platform for PeakShavr."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, NAME
from .coordinator import PeakShavrCoordinator
from .entity_helpers import load_device_info, load_key

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class PeakShavrSensorDescription(SensorEntityDescription):
    """PeakShavr sensor description."""

    value_key: str


SENSOR_DESCRIPTIONS: tuple[PeakShavrSensorDescription, ...] = (
    PeakShavrSensorDescription(
        key="projected_avg_kw",
        translation_key="projected_avg_kw",
        value_key="projected_avg_kw",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        suggested_display_precision=2,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    PeakShavrSensorDescription(
        key="headroom_kw",
        translation_key="headroom_kw",
        value_key="headroom_kw",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        suggested_display_precision=2,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    PeakShavrSensorDescription(
        key="monthly_peak_kw",
        translation_key="monthly_peak_kw",
        value_key="monthly_peak_kw",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        suggested_display_precision=2,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    PeakShavrSensorDescription(
        key="active_shed_count",
        translation_key="active_shed_count",
        value_key="active_shed_count",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up PeakShavr sensors from config entry."""
    coordinator: PeakShavrCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            PeakShavrSensor(coordinator, entry, description)
            for description in SENSOR_DESCRIPTIONS
        ]
        + [PeakShavrLastActionSensor(coordinator, entry)]
    )

    by_subentry: dict[str | None, list[SensorEntity]] = {}
    for load in coordinator.load_configs:
        by_subentry.setdefault(load.config_subentry_id, []).append(
            PeakShavrLoadCurrentDrawSensor(coordinator, entry, load.entity_id)
        )

    for subentry_id, entities in by_subentry.items():
        if subentry_id is None:
            async_add_entities(entities)
            continue
        async_add_entities(entities, config_subentry_id=subentry_id)


class PeakShavrSensor(CoordinatorEntity[PeakShavrCoordinator], SensorEntity):
    """Diagnostic numeric sensor."""

    entity_description: PeakShavrSensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: PeakShavrCoordinator,
        entry: ConfigEntry,
        description: PeakShavrSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": NAME,
            "manufacturer": NAME,
        }

    @property
    def native_value(self) -> Any:
        key = self.entity_description.value_key
        if key == "projected_avg_kw":
            return self.coordinator.projected_avg_kw
        if key == "headroom_kw":
            return self.coordinator.headroom_kw
        if key == "monthly_peak_kw":
            return self.coordinator.monthly_peak_kw
        if key == "active_shed_count":
            return self.coordinator.active_shed_count
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self.coordinator.extra_state_attributes()


class PeakShavrLastActionSensor(CoordinatorEntity[PeakShavrCoordinator], SensorEntity):
    """Sensor exposing the latest controller action."""

    _attr_has_entity_name = True
    _attr_name = "Last action"
    _attr_translation_key = "last_action"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: PeakShavrCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_last_action"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": NAME,
            "manufacturer": NAME,
        }

    @property
    def native_value(self) -> str:
        return self.coordinator.last_action

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self.coordinator.extra_state_attributes()


class PeakShavrLoadCurrentDrawSensor(
    CoordinatorEntity[PeakShavrCoordinator], SensorEntity
):
    """Diagnostic sensor exposing current per-load power draw."""

    _attr_has_entity_name = True
    _attr_name = "Current draw"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_native_unit_of_measurement = UnitOfPower.KILO_WATT
    _attr_suggested_display_precision = 2

    def __init__(
        self,
        coordinator: PeakShavrCoordinator,
        entry: ConfigEntry,
        load_entity_id: str,
    ) -> None:
        super().__init__(coordinator)
        self._load_entity_id = load_entity_id
        self._attr_unique_id = f"{entry.entry_id}_{load_key(load_entity_id)}_current_draw_kw"
        self._attr_device_info = load_device_info(coordinator, entry, load_entity_id)

    @property
    def native_value(self) -> float | None:
        return self.coordinator.load_live_kw(self._load_entity_id)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        load = self.coordinator.get_load_config(self._load_entity_id)
        return {
            "managed_entity_id": self._load_entity_id,
            "priority": load.priority if load else None,
            "expected_source_mode": load.expected_source_mode if load else None,
            "power_sensor": load.power_sensor if load else None,
            "manual_expected_kw": load.manual_expected_kw if load else None,
            "expected_kw": self.coordinator.load_expected_kw(self._load_entity_id),
            "min_required_kw": load.min_required_kw if load else None,
            "threshold_reference_kw": self.coordinator.load_threshold_reference_kw(
                self._load_entity_id
            ),
            "shed_by_controller": self.coordinator.is_load_shed(self._load_entity_id),
            "external_override": self.coordinator.is_load_external_override(
                self._load_entity_id
            ),
            "blocked_by_min_required_draw": self.coordinator.load_blocked_by_threshold(
                self._load_entity_id
            ),
        }
