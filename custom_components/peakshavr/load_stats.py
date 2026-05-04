"""Load-power statistics helpers."""

from __future__ import annotations

from collections import deque
from statistics import quantiles

from .const import DEFAULT_LOAD_EXPECTED_KW


class RollingLoadStats:
    """Track rolling on-state power samples for one load."""

    __slots__ = ("_samples",)

    def __init__(self, samples: list[float] | None = None, max_samples: int = 240) -> None:
        self._samples: deque[float] = deque(maxlen=max_samples)
        for sample in samples or []:
            self.add_sample(sample)

    @property
    def sample_count(self) -> int:
        return len(self._samples)

    def add_sample(self, sample_kw: float) -> None:
        if sample_kw <= 0:
            return
        self._samples.append(float(sample_kw))

    def p90(self) -> float | None:
        if not self._samples:
            return None
        if len(self._samples) == 1:
            return self._samples[0]
        return quantiles(self._samples, n=10, method="inclusive")[8]

    def as_list(self) -> list[float]:
        return list(self._samples)


def resolve_expected_load_kw(
    *,
    manual_expected_kw: float | None,
    live_sensor_kw: float | None,
    stats_p90_kw: float | None,
) -> float:
    """Resolve conservative expected draw in kW for control decisions."""
    if manual_expected_kw is not None and manual_expected_kw > 0:
        return manual_expected_kw
    if stats_p90_kw is not None and stats_p90_kw > 0:
        return stats_p90_kw
    if live_sensor_kw is not None and live_sensor_kw > 0:
        return live_sensor_kw
    return DEFAULT_LOAD_EXPECTED_KW

