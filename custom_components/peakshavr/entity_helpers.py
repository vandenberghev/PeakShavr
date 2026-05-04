"""Entity and device helper functions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN, NAME

if TYPE_CHECKING:
    from .coordinator import PeakShavrCoordinator


def load_key(load_entity_id: str) -> str:
    """Stable key fragment for load-specific entities."""
    return load_entity_id.replace(".", "_")


def load_device_identifier(entry: ConfigEntry, load_entity_id: str) -> str:
    """Stable device identifier key for one managed load."""
    return f"{entry.entry_id}:{load_entity_id}"


def load_device_info(
    coordinator: PeakShavrCoordinator,
    entry: ConfigEntry,
    load_entity_id: str,
) -> dict[str, Any]:
    """Build Home Assistant device_info payload for one managed load."""
    return {
        "identifiers": {(DOMAIN, load_device_identifier(entry, load_entity_id))},
        "name": coordinator.load_device_name(load_entity_id),
        "manufacturer": NAME,
        "via_device": (DOMAIN, entry.entry_id),
    }
