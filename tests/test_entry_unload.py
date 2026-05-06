"""Tests for config-entry unload lifecycle."""

from __future__ import annotations

import asyncio
import importlib
import sys
import types
from types import SimpleNamespace

from custom_components.peakshavr.const import DOMAIN, PLATFORMS

integration = importlib.import_module("custom_components.peakshavr")


class _CoordinatorStub:
    def __init__(self) -> None:
        self.shutdown_calls = 0

    async def async_shutdown(self) -> None:
        self.shutdown_calls += 1


class _ConfigEntriesStub:
    def __init__(self, *, unload_ok: bool) -> None:
        self._unload_ok = unload_ok
        self.calls: list[tuple[object, tuple[object, ...]]] = []

    async def async_unload_platforms(self, entry: object, platforms: list[object]) -> bool:
        self.calls.append((entry, tuple(platforms)))
        return self._unload_ok


def _install_coordinator_stub_module(monkeypatch) -> None:
    module = types.ModuleType("custom_components.peakshavr.coordinator")
    module.PeakShavrCoordinator = _CoordinatorStub
    monkeypatch.setitem(sys.modules, "custom_components.peakshavr.coordinator", module)


def test_async_unload_entry_keeps_runtime_when_platform_unload_fails(monkeypatch) -> None:
    _install_coordinator_stub_module(monkeypatch)
    entry = SimpleNamespace(entry_id="entry-1")
    coordinator = _CoordinatorStub()
    config_entries = _ConfigEntriesStub(unload_ok=False)
    hass = SimpleNamespace(
        config_entries=config_entries,
        data={DOMAIN: {entry.entry_id: coordinator}},
    )

    unload_ok = asyncio.run(integration.async_unload_entry(hass, entry))

    assert unload_ok is False
    assert coordinator.shutdown_calls == 0
    assert hass.data[DOMAIN][entry.entry_id] is coordinator
    assert config_entries.calls == [(entry, tuple(PLATFORMS))]


def test_async_unload_entry_shuts_down_runtime_after_successful_unload(monkeypatch) -> None:
    _install_coordinator_stub_module(monkeypatch)
    entry = SimpleNamespace(entry_id="entry-1")
    coordinator = _CoordinatorStub()
    config_entries = _ConfigEntriesStub(unload_ok=True)
    hass = SimpleNamespace(
        config_entries=config_entries,
        data={DOMAIN: {entry.entry_id: coordinator}},
    )

    unload_ok = asyncio.run(integration.async_unload_entry(hass, entry))

    assert unload_ok is True
    assert coordinator.shutdown_calls == 1
    assert DOMAIN not in hass.data
    assert config_entries.calls == [(entry, tuple(PLATFORMS))]
