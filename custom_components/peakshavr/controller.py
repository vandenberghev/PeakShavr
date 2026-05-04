"""Pure controller decision helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .projection import (
    calculate_projected_average_kw,
    calculate_projected_average_with_added_load,
)


@dataclass(slots=True, frozen=True)
class ShedCandidate:
    """One load candidate for shedding."""

    entity_id: str
    priority: int
    expected_kw: float
    blocked_by_min_on_time: bool
    blocked_by_min_required_draw: bool


@dataclass(slots=True, frozen=True)
class RestoreCandidate:
    """One load candidate for restoring."""

    entity_id: str
    expected_kw: float
    blocked_by_cooldown: bool
    blocked_by_backoff: bool


def select_shed_plan(
    *,
    projected_avg_kw: float,
    target_kw: float,
    used_kwh: float,
    live_kw: float,
    remaining_seconds: int,
    is_escalation: bool,
    candidates: list[ShedCandidate],
) -> list[str]:
    """Select one or more loads to shed."""
    if projected_avg_kw <= target_kw or not candidates:
        return []

    selected: list[str] = []
    max_actions = len(candidates) if is_escalation else 1
    working_projection = projected_avg_kw
    working_live_kw = live_kw

    for candidate in sorted(candidates, key=lambda item: (item.priority, item.entity_id)):
        if candidate.blocked_by_min_on_time and not is_escalation:
            continue
        if candidate.blocked_by_min_required_draw and not is_escalation:
            continue

        selected.append(candidate.entity_id)
        working_live_kw = max(0.0, working_live_kw - candidate.expected_kw)
        working_projection = calculate_projected_average_kw(
            used_kwh=used_kwh,
            live_kw=working_live_kw,
            remaining_seconds=remaining_seconds,
        )

        if len(selected) >= max_actions or working_projection <= target_kw:
            break

    return selected


def select_restore_candidate(
    *,
    target_kw: float,
    used_kwh: float,
    live_kw: float,
    remaining_seconds: int,
    degraded: bool,
    shed_stack: list[str],
    restore_candidates: dict[str, RestoreCandidate],
    now: datetime,
) -> str | None:
    """Select one load to restore, last-shed-first."""
    if degraded:
        return None

    for entity_id in reversed(shed_stack):
        candidate = restore_candidates.get(entity_id)
        if candidate is None:
            continue
        if candidate.blocked_by_backoff or candidate.blocked_by_cooldown:
            continue
        projected_with_load = calculate_projected_average_with_added_load(
            used_kwh=used_kwh,
            live_kw=live_kw,
            load_expected_kw=candidate.expected_kw,
            remaining_seconds=remaining_seconds,
        )
        if projected_with_load <= target_kw:
            return entity_id
    return None
