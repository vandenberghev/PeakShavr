"""Tests for quarter and month time helpers."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from custom_components.peakshavr.time_utils import (
    BELGIUM_TIME_ZONE,
    month_key,
    quarter_elapsed_and_remaining_seconds,
    quarter_start,
)


def test_quarter_start_flooring() -> None:
    moment = datetime(2026, 5, 4, 21, 17, 42, tzinfo=BELGIUM_TIME_ZONE)
    assert quarter_start(moment) == datetime(
        2026, 5, 4, 21, 15, 0, tzinfo=BELGIUM_TIME_ZONE
    )


def test_elapsed_and_remaining_sum_to_quarter_length() -> None:
    moment = datetime(2026, 5, 4, 21, 17, 42, tzinfo=BELGIUM_TIME_ZONE)
    elapsed, remaining = quarter_elapsed_and_remaining_seconds(moment)
    assert elapsed + remaining == 900
    assert elapsed == 162
    assert remaining == 738


def test_month_key_uses_local_timezone() -> None:
    utc = ZoneInfo("UTC")
    moment = datetime(2026, 2, 28, 23, 30, tzinfo=utc)
    # In Belgium this is already March 1st.
    assert month_key(moment) == "2026-03"


def test_dst_spring_forward_keeps_clock_aligned_quarter() -> None:
    # 2026-03-29 jumps from 02:00 to 03:00 in Europe/Brussels.
    moment = datetime(2026, 3, 29, 3, 2, tzinfo=BELGIUM_TIME_ZONE)
    assert quarter_start(moment) == datetime(
        2026, 3, 29, 3, 0, 0, tzinfo=BELGIUM_TIME_ZONE
    )


def test_dst_fall_back_has_valid_quarter_floor() -> None:
    # 2026-10-25 repeats 02:00; ensure flooring remains deterministic.
    moment = datetime(2026, 10, 25, 2, 47, tzinfo=BELGIUM_TIME_ZONE)
    floored = quarter_start(moment)
    assert floored.minute == 45
    assert floored.second == 0

