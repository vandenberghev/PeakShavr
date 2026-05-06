"""Tests for coordinator service-call failure handling."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import importlib
import sys
import types
from types import SimpleNamespace

import pytest


def _import_coordinator_with_stubs(monkeypatch):
    homeassistant = types.ModuleType("homeassistant")
    homeassistant.__path__ = []

    config_entries = types.ModuleType("homeassistant.config_entries")

    class ConfigEntry:
        pass

    config_entries.ConfigEntry = ConfigEntry

    const = types.ModuleType("homeassistant.const")
    const.ATTR_ENTITY_ID = "entity_id"
    const.SERVICE_TURN_OFF = "turn_off"
    const.SERVICE_TURN_ON = "turn_on"
    const.STATE_OFF = "off"
    const.STATE_ON = "on"
    const.STATE_UNAVAILABLE = "unavailable"
    const.STATE_UNKNOWN = "unknown"

    core = types.ModuleType("homeassistant.core")
    core.Event = dict
    core.EventStateChangedData = dict
    core.EventStateReportedData = dict

    class HomeAssistant:
        pass

    core.HomeAssistant = HomeAssistant

    exceptions = types.ModuleType("homeassistant.exceptions")

    class HomeAssistantError(Exception):
        pass

    class ConfigEntryNotReady(HomeAssistantError):
        pass

    exceptions.HomeAssistantError = HomeAssistantError
    exceptions.ConfigEntryNotReady = ConfigEntryNotReady

    helpers = types.ModuleType("homeassistant.helpers")
    helpers.__path__ = []
    helpers_event = types.ModuleType("homeassistant.helpers.event")
    helpers_event.async_track_state_change_event = lambda *args, **kwargs: lambda: None
    helpers_event.async_track_state_report_event = lambda *args, **kwargs: lambda: None
    helpers_event.async_track_utc_time_change = lambda *args, **kwargs: lambda: None

    helpers_update_coordinator = types.ModuleType(
        "homeassistant.helpers.update_coordinator"
    )

    class DataUpdateCoordinator:
        def __class_getitem__(cls, _item):
            return cls

        def __init__(self, hass, logger, **kwargs) -> None:
            self.hass = hass
            self.logger = logger
            self.kwargs = kwargs

        async def async_config_entry_first_refresh(self) -> None:
            return None

        def async_set_updated_data(self, _data) -> None:
            return None

    helpers_update_coordinator.DataUpdateCoordinator = DataUpdateCoordinator

    util = types.ModuleType("homeassistant.util")
    util.__path__ = []
    dt = types.ModuleType("homeassistant.util.dt")
    dt.utcnow = lambda: datetime.now(timezone.utc)
    dt.UTC = timezone.utc
    dt.get_time_zone = lambda _name: timezone.utc

    store_module = types.ModuleType("custom_components.peakshavr.store")

    class PeakShavrStore:
        def __init__(self, hass, entry_id: str) -> None:
            self.hass = hass
            self.entry_id = entry_id

        async def async_load(self):
            return None

        async def async_save(self, _payload) -> None:
            return None

    store_module.PeakShavrStore = PeakShavrStore

    validation_module = types.ModuleType("custom_components.peakshavr.validation")

    class _ValidationResult:
        def __init__(self, ok: bool, error_key: str | None = None) -> None:
            self.ok = ok
            self.error_key = error_key

    validation_module.energy_state_to_kwh = lambda _state: None
    validation_module.power_state_to_kw = lambda _state: None
    validation_module.validate_energy_entity_state = lambda _state: _ValidationResult(True)
    validation_module.validate_power_entity_state = lambda _state: _ValidationResult(True)

    monkeypatch.setitem(sys.modules, "homeassistant", homeassistant)
    monkeypatch.setitem(sys.modules, "homeassistant.config_entries", config_entries)
    monkeypatch.setitem(sys.modules, "homeassistant.const", const)
    monkeypatch.setitem(sys.modules, "homeassistant.core", core)
    monkeypatch.setitem(sys.modules, "homeassistant.exceptions", exceptions)
    monkeypatch.setitem(sys.modules, "homeassistant.helpers", helpers)
    monkeypatch.setitem(sys.modules, "homeassistant.helpers.event", helpers_event)
    monkeypatch.setitem(
        sys.modules,
        "homeassistant.helpers.update_coordinator",
        helpers_update_coordinator,
    )
    monkeypatch.setitem(sys.modules, "homeassistant.util", util)
    monkeypatch.setitem(sys.modules, "homeassistant.util.dt", dt)
    monkeypatch.setitem(sys.modules, "custom_components.peakshavr.store", store_module)
    monkeypatch.setitem(
        sys.modules,
        "custom_components.peakshavr.validation",
        validation_module,
    )

    sys.modules.pop("custom_components.peakshavr.coordinator", None)
    return importlib.import_module("custom_components.peakshavr.coordinator")


def test_async_call_load_service_clears_pending_on_failure(monkeypatch) -> None:
    coordinator_module = _import_coordinator_with_stubs(monkeypatch)
    coordinator = coordinator_module.PeakShavrCoordinator.__new__(
        coordinator_module.PeakShavrCoordinator
    )

    class _Services:
        async def async_call(self, _domain, _service, _data, *, blocking: bool) -> None:
            assert blocking is True
            raise coordinator_module.HomeAssistantError("service failed")

    coordinator.hass = SimpleNamespace(services=_Services())
    coordinator._pending_service_actions = {}

    with pytest.raises(coordinator_module.HomeAssistantError):
        asyncio.run(
            coordinator._async_call_load_service("switch.boiler", turn_on=False)
        )

    assert coordinator._pending_service_actions == {}


def test_async_apply_shed_actions_continues_after_failure(monkeypatch) -> None:
    coordinator_module = _import_coordinator_with_stubs(monkeypatch)
    coordinator = coordinator_module.PeakShavrCoordinator.__new__(
        coordinator_module.PeakShavrCoordinator
    )
    coordinator._shed_stack = []
    coordinator._last_shed_at = {}
    coordinator._external_overrides = {"switch.a", "switch.b", "switch.c"}

    calls: list[str] = []

    async def _call_load_service(entity_id: str, *, turn_on: bool) -> None:
        assert turn_on is False
        calls.append(entity_id)
        if entity_id == "switch.a":
            raise coordinator_module.HomeAssistantError("cannot shed")

    coordinator._async_call_load_service = _call_load_service
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)

    successful, failed = asyncio.run(
        coordinator._async_apply_shed_actions(
            now=now,
            planned_sheds=["switch.a", "switch.b", "switch.c"],
        )
    )

    assert calls == ["switch.a", "switch.b", "switch.c"]
    assert successful == ["switch.b", "switch.c"]
    assert failed == ["switch.a"]
    assert coordinator._shed_stack == ["switch.b", "switch.c"]
    assert coordinator._last_shed_at == {"switch.b": now, "switch.c": now}
    assert coordinator._external_overrides == {"switch.a"}
