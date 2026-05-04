"""Projection and telemetry confidence math."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class ProjectionSnapshot:
    """Calculated quarter projection state."""

    used_kwh: float
    live_kw: float
    elapsed_seconds: int
    remaining_seconds: int
    projected_avg_kw: float
    observed_avg_kw: float


def build_projection(
    used_kwh: float,
    live_kw: float,
    elapsed_seconds: int,
    remaining_seconds: int,
) -> ProjectionSnapshot:
    """Calculate projected quarter-end average kW."""
    observed_avg_kw = calculate_observed_average_kw(used_kwh, elapsed_seconds)
    projected_avg_kw = calculate_projected_average_kw(used_kwh, live_kw, remaining_seconds)
    return ProjectionSnapshot(
        used_kwh=used_kwh,
        live_kw=live_kw,
        elapsed_seconds=elapsed_seconds,
        remaining_seconds=remaining_seconds,
        projected_avg_kw=projected_avg_kw,
        observed_avg_kw=observed_avg_kw,
    )


def calculate_projected_average_kw(
    used_kwh: float,
    live_kw: float,
    remaining_seconds: int,
) -> float:
    """Projected quarter-end average in kW."""
    projected_kwh = used_kwh + (live_kw * max(0, remaining_seconds) / 3600)
    return projected_kwh * 4


def calculate_projected_average_with_added_load(
    used_kwh: float,
    live_kw: float,
    load_expected_kw: float,
    remaining_seconds: int,
) -> float:
    """Projected quarter-end average if one load is restored."""
    return calculate_projected_average_kw(
        used_kwh=used_kwh,
        live_kw=live_kw + max(0.0, load_expected_kw),
        remaining_seconds=remaining_seconds,
    )


def calculate_observed_average_kw(used_kwh: float, elapsed_seconds: int) -> float:
    """Observed average import kW so far in quarter."""
    if elapsed_seconds <= 0:
        return 0.0
    return used_kwh / (elapsed_seconds / 3600)


def telemetry_conflict(
    live_kw: float,
    observed_avg_kw: float,
    conflict_abs_kw: float,
    conflict_rel: float,
) -> bool:
    """Decide if power telemetry conflicts with energy-derived demand."""
    absolute_gap = abs(observed_avg_kw - live_kw)
    dominant = max(abs(observed_avg_kw), abs(live_kw), 0.001)
    relative_gap = absolute_gap / dominant
    return absolute_gap > conflict_abs_kw or relative_gap > conflict_rel

