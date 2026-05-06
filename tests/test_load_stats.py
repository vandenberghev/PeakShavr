"""Tests for load statistics helpers."""

from __future__ import annotations

from custom_components.peakshavr.const import (
    LOAD_EXPECTED_SOURCE_MANUAL,
    LOAD_EXPECTED_SOURCE_SENSOR,
)
from custom_components.peakshavr.load_stats import RollingLoadStats, resolve_expected_load_kw


def test_rolling_stats_p90() -> None:
    stats = RollingLoadStats()
    for sample in [1.0, 1.5, 2.0, 2.5, 3.0]:
        stats.add_sample(sample)
    assert round(stats.p90() or 0, 2) == 2.8


def test_expected_kw_prefers_manual() -> None:
    value = resolve_expected_load_kw(
        manual_expected_kw=2.2,
        live_sensor_kw=1.0,
        stats_p90_kw=1.8,
        expected_source_mode=LOAD_EXPECTED_SOURCE_MANUAL,
    )
    assert value == 2.2


def test_expected_kw_sensor_mode_ignores_manual() -> None:
    value = resolve_expected_load_kw(
        manual_expected_kw=2.2,
        live_sensor_kw=1.0,
        stats_p90_kw=1.8,
        expected_source_mode=LOAD_EXPECTED_SOURCE_SENSOR,
    )
    assert value == 1.8


def test_expected_kw_falls_back_to_stats_then_sensor_in_sensor_mode() -> None:
    value_from_stats = resolve_expected_load_kw(
        manual_expected_kw=None,
        live_sensor_kw=1.0,
        stats_p90_kw=1.8,
        expected_source_mode=LOAD_EXPECTED_SOURCE_SENSOR,
    )
    assert value_from_stats == 1.8

    value_from_sensor = resolve_expected_load_kw(
        manual_expected_kw=None,
        live_sensor_kw=1.3,
        stats_p90_kw=None,
        expected_source_mode=LOAD_EXPECTED_SOURCE_SENSOR,
    )
    assert value_from_sensor == 1.3
