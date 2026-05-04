"""Tests for projection and telemetry math."""

from __future__ import annotations

from custom_components.peakshavr.projection import (
    build_projection,
    calculate_projected_average_with_added_load,
    telemetry_conflict,
)


def test_projection_formula_matches_quarter_math() -> None:
    snapshot = build_projection(
        used_kwh=0.30,
        live_kw=2.0,
        elapsed_seconds=300,
        remaining_seconds=600,
    )
    # 0.30 + (2.0 * 600 / 3600) = 0.633333... kWh quarter total => *4
    assert round(snapshot.projected_avg_kw, 3) == 2.533


def test_projection_with_added_load() -> None:
    projected = calculate_projected_average_with_added_load(
        used_kwh=0.20,
        live_kw=1.0,
        load_expected_kw=1.5,
        remaining_seconds=300,
    )
    # (0.20 + (2.5 * 300 / 3600)) * 4 = 1.633333...
    assert round(projected, 3) == 1.633


def test_telemetry_conflict_detects_large_mismatch() -> None:
    assert telemetry_conflict(
        live_kw=0.5,
        observed_avg_kw=2.0,
        conflict_abs_kw=0.2,
        conflict_rel=0.15,
    )


def test_telemetry_conflict_ignores_small_gap() -> None:
    assert not telemetry_conflict(
        live_kw=1.95,
        observed_avg_kw=2.0,
        conflict_abs_kw=0.2,
        conflict_rel=0.15,
    )

