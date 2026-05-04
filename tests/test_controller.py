"""Tests for shed/restore decision helpers."""

from __future__ import annotations

from datetime import datetime, timezone

from custom_components.peakshavr.controller import (
    RestoreCandidate,
    ShedCandidate,
    select_restore_candidate,
    select_shed_plan,
)


def test_select_shed_plan_limits_to_one_outside_escalation() -> None:
    selected = select_shed_plan(
        projected_avg_kw=5.0,
        target_kw=3.0,
        used_kwh=0.5,
        live_kw=4.0,
        remaining_seconds=300,
        is_escalation=False,
        candidates=[
            ShedCandidate("switch.a", priority=1, expected_kw=1.5, blocked_by_min_on_time=False),
            ShedCandidate("switch.b", priority=2, expected_kw=1.5, blocked_by_min_on_time=False),
        ],
    )
    assert selected == ["switch.a"]


def test_select_shed_plan_can_shed_multiple_in_escalation() -> None:
    selected = select_shed_plan(
        projected_avg_kw=4.333,
        target_kw=3.0,
        used_kwh=1.0,
        live_kw=5.0,
        remaining_seconds=60,
        is_escalation=True,
        candidates=[
            ShedCandidate("switch.a", priority=1, expected_kw=1.0, blocked_by_min_on_time=False),
            ShedCandidate("switch.b", priority=2, expected_kw=1.0, blocked_by_min_on_time=False),
            ShedCandidate("switch.c", priority=3, expected_kw=1.0, blocked_by_min_on_time=False),
        ],
    )
    assert selected == ["switch.a", "switch.b", "switch.c"]


def test_select_restore_candidate_is_last_shed_first() -> None:
    chosen = select_restore_candidate(
        target_kw=3.0,
        used_kwh=0.4,
        live_kw=1.0,
        remaining_seconds=120,
        degraded=False,
        shed_stack=["switch.a", "switch.b", "switch.c"],
        restore_candidates={
            "switch.a": RestoreCandidate(
                "switch.a",
                expected_kw=0.8,
                blocked_by_cooldown=False,
                blocked_by_backoff=False,
            ),
            "switch.b": RestoreCandidate(
                "switch.b",
                expected_kw=0.8,
                blocked_by_cooldown=False,
                blocked_by_backoff=False,
            ),
            "switch.c": RestoreCandidate(
                "switch.c",
                expected_kw=0.8,
                blocked_by_cooldown=False,
                blocked_by_backoff=False,
            ),
        },
        now=datetime.now(timezone.utc),
    )
    assert chosen == "switch.c"


def test_select_restore_candidate_freezes_when_degraded() -> None:
    chosen = select_restore_candidate(
        target_kw=3.0,
        used_kwh=0.4,
        live_kw=1.0,
        remaining_seconds=120,
        degraded=True,
        shed_stack=["switch.a"],
        restore_candidates={
            "switch.a": RestoreCandidate(
                "switch.a",
                expected_kw=0.5,
                blocked_by_cooldown=False,
                blocked_by_backoff=False,
            )
        },
        now=datetime.now(timezone.utc),
    )
    assert chosen is None


def test_select_shed_plan_escalation_overrides_min_on_time() -> None:
    """In escalation mode a load blocked by min-on-time MUST still be shed."""
    selected = select_shed_plan(
        projected_avg_kw=5.0,
        target_kw=3.0,
        used_kwh=0.5,
        live_kw=4.0,
        remaining_seconds=60,
        is_escalation=True,
        candidates=[
            ShedCandidate(
                "switch.a", priority=1, expected_kw=2.5, blocked_by_min_on_time=True
            ),
        ],
    )
    assert selected == ["switch.a"]


def test_select_shed_plan_min_on_time_blocks_outside_escalation() -> None:
    """Outside escalation, loads blocked by min-on-time must NOT be shed."""
    selected = select_shed_plan(
        projected_avg_kw=5.0,
        target_kw=3.0,
        used_kwh=0.5,
        live_kw=4.0,
        remaining_seconds=300,
        is_escalation=False,
        candidates=[
            ShedCandidate(
                "switch.a", priority=1, expected_kw=2.5, blocked_by_min_on_time=True
            ),
        ],
    )
    assert selected == []


def test_select_shed_plan_returns_empty_when_no_candidates() -> None:
    """Coordinator filtering all candidates (e.g. all under backoff) yields no sheds."""
    selected = select_shed_plan(
        projected_avg_kw=5.0,
        target_kw=3.0,
        used_kwh=0.5,
        live_kw=4.0,
        remaining_seconds=300,
        is_escalation=False,
        candidates=[],
    )
    assert selected == []
