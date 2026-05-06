"""PeakShavr integration bootstrap."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

from .const import CONF_LOAD_ENTITY_ID, CONF_LOADS, DOMAIN, PLATFORMS, SUBENTRY_TYPE_LOAD
from .models import LoadConfig

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry, ConfigSubentry
    from homeassistant.core import HomeAssistant

    from .coordinator import PeakShavrCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate config entry to subentry-backed load storage."""
    from homeassistant.config_entries import ConfigSubentry

    if entry.version > 2:
        _LOGGER.error("Cannot migrate %s config entry version %s", DOMAIN, entry.version)
        return False

    if entry.version < 2:
        _LOGGER.debug("Migrating %s config entry %s to version 2", DOMAIN, entry.entry_id)

    options = dict(entry.options)
    raw_option_loads = options.get(CONF_LOADS, [])
    has_mapped_load_subentries = any(
        subentry.subentry_type == SUBENTRY_TYPE_LOAD for subentry in entry.subentries.values()
    )
    if raw_option_loads and not has_mapped_load_subentries:
        known_load_ids = {
            _subentry_load_entity_id(subentry)
            for subentry in entry.subentries.values()
            if subentry.subentry_type == SUBENTRY_TYPE_LOAD
        }
        for raw_load in raw_option_loads:
            if not isinstance(raw_load, Mapping):
                continue
            load = LoadConfig.from_mapping(dict(raw_load))
            if load.entity_id in known_load_ids:
                continue
            hass.config_entries.async_add_subentry(
                entry,
                ConfigSubentry(
                    subentry_type=SUBENTRY_TYPE_LOAD,
                    title=load.entity_id,
                    unique_id=load.entity_id,
                    data=MappingProxyType(load.as_mapping()),
                ),
            )
            known_load_ids.add(load.entity_id)

    if raw_option_loads:
        options.pop(CONF_LOADS, None)

    hass.config_entries.async_update_entry(entry, version=2, options=options)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up PeakShavr from a config entry."""
    from .coordinator import PeakShavrCoordinator

    coordinator = PeakShavrCoordinator(hass, entry)
    await coordinator.async_initialize()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    from .coordinator import PeakShavrCoordinator

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    coordinator: PeakShavrCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
    await coordinator.async_shutdown()
    if not hass.data[DOMAIN]:
        hass.data.pop(DOMAIN)
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


def _subentry_load_entity_id(subentry: Any) -> str | None:
    unique_id = subentry.unique_id
    if isinstance(unique_id, str) and unique_id:
        return unique_id
    raw_entity_id = subentry.data.get(CONF_LOAD_ENTITY_ID)
    if isinstance(raw_entity_id, str) and raw_entity_id:
        return raw_entity_id
    return None
