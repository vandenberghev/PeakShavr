"""Runtime coordinator for PeakShavr."""

from __future__ import annotations

from collections import deque
from datetime import datetime, timedelta
import logging
from collections.abc import Callable
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import Event, EventStateChangedData, EventStateReportedData, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_state_report_event,
    async_track_utc_time_change,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .config import RuntimeConfig, resolve_runtime_config
from .const import (
    ATTR_DEGRADED_REASON,
    ATTR_UNCERTAIN_QUARTER,
    CONF_ENABLED,
    DEFAULT_ESCALATION_INTERVAL_SECONDS,
    DOMAIN,
    ENERGY_MODE_TOTAL,
    MAX_PLAUSIBLE_QUARTER_KWH,
)
from .controller import RestoreCandidate, ShedCandidate, select_restore_candidate, select_shed_plan
from .load_stats import RollingLoadStats, resolve_expected_load_kw
from .models import LoadConfig
from .projection import build_projection, telemetry_conflict
from .store import PeakShavrStore
from .time_utils import month_key, quarter_elapsed_and_remaining_seconds, quarter_start
from .validation import (
    energy_state_to_kwh,
    power_state_to_kw,
    validate_energy_entity_state,
    validate_power_entity_state,
)

_LOGGER = logging.getLogger(__name__)


class PeakShavrCoordinator(DataUpdateCoordinator[None]):
    """Coordinates peak-shaving calculations and load control."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_ESCALATION_INTERVAL_SECONDS),
        )
        self._runtime_config: RuntimeConfig = resolve_runtime_config(config_entry)
        self._storage = PeakShavrStore(hass, config_entry.entry_id)

        self._quarter_start_local: datetime | None = None
        self._energy_at_quarter_start_kwh: float | None = None
        self._monthly_peak_kw: float = 0.0
        self._monthly_peak_ts: datetime | None = None
        self._month_key: str | None = None
        self._uncertain_quarter = False
        self._enabled = self._runtime_config.enabled

        self._projected_avg_kw: float | None = None
        self._headroom_kw: float | None = None
        self._degraded_reason: str | None = None
        self._escalation_active = False
        self._last_action = "initialized"

        self._shed_stack: list[str] = []
        self._last_shed_at: dict[str, datetime] = {}
        self._last_restore_at: dict[str, datetime] = {}
        self._override_backoff_until: dict[str, datetime] = {}
        self._external_overrides: set[str] = set()
        self._pending_service_actions: dict[str, tuple[str, datetime]] = {}

        self._power_last_reported_at: datetime | None = None
        self._power_last_reported_kw: float | None = None
        self._last_control_run_at: datetime | None = None

        self._energy_samples: dict[str, deque[tuple[datetime, float]]] = {}
        self._load_stats: dict[str, RollingLoadStats] = {}

        self._unsubscribers: list[Callable[[], None]] = []

    @property
    def runtime_config(self) -> RuntimeConfig:
        return self._runtime_config

    @property
    def projected_avg_kw(self) -> float | None:
        return self._projected_avg_kw

    @property
    def headroom_kw(self) -> float | None:
        return self._headroom_kw

    @property
    def monthly_peak_kw(self) -> float:
        return self._monthly_peak_kw

    @property
    def monthly_peak_timestamp(self) -> datetime | None:
        return self._monthly_peak_ts

    @property
    def active_shed_count(self) -> int:
        return len(self._shed_stack)

    @property
    def escalation_active(self) -> bool:
        return self._escalation_active

    @property
    def degraded_reason(self) -> str | None:
        return self._degraded_reason

    @property
    def uncertain_quarter(self) -> bool:
        return self._uncertain_quarter

    @property
    def last_action(self) -> str:
        return self._last_action

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def external_overrides(self) -> list[str]:
        return sorted(self._external_overrides)

    async def async_initialize(self) -> None:
        """Initialize runtime and register listeners."""
        self._validate_required_entities()
        self._restore_or_initialize_time_state()
        await self._async_restore_persisted_state()
        self._register_listeners()
        await self.async_config_entry_first_refresh()

    async def async_shutdown(self) -> None:
        """Stop callbacks and persist state."""
        while self._unsubscribers:
            self._unsubscribers.pop()()
        await self._async_save_state()

    async def async_set_enabled(self, enabled: bool) -> None:
        """Enable or disable the controller."""
        if self._enabled == enabled:
            return
        self._enabled = enabled
        self._last_action = "controller enabled" if enabled else "controller disabled"
        await self._async_save_state()
        self.async_set_updated_data(None)

    def _validate_required_entities(self) -> None:
        """Validate configured source entities exist and have correct metadata."""
        power_state = self.hass.states.get(self._runtime_config.power_sensor)
        power_validation = validate_power_entity_state(power_state)
        if not power_validation.ok:
            raise ConfigEntryNotReady(
                f"Power sensor invalid: {self._runtime_config.power_sensor} ({power_validation.error_key})"
            )

        for entity_id in self._runtime_config.energy_entity_ids:
            energy_state = self.hass.states.get(entity_id)
            energy_validation = validate_energy_entity_state(energy_state)
            if not energy_validation.ok:
                raise ConfigEntryNotReady(
                    f"Energy sensor invalid: {entity_id} ({energy_validation.error_key})"
                )

        # Require newer Home Assistant state model with report timestamps.
        if power_state is not None and getattr(power_state, "last_reported", None) is None:
            raise ConfigEntryNotReady(
                "Home Assistant version missing state_reported support for telemetry confidence"
            )

    def _restore_or_initialize_time_state(self) -> None:
        """Initialize quarter and month state from current time."""
        now_local = dt_util.utcnow().astimezone(dt_util.get_time_zone("Europe/Brussels"))
        self._quarter_start_local = quarter_start(now_local)
        self._month_key = month_key(now_local)

    async def _async_restore_persisted_state(self) -> None:
        """Restore persisted state where possible."""
        persisted = await self._storage.async_load()
        for load in self._runtime_config.loads:
            self._load_stats[load.entity_id] = RollingLoadStats()

        self._seed_samples_from_current_states()
        if not persisted:
            self._initialize_baseline_from_current_energy(uncertain=True)
            await self._async_save_state()
            return

        self._enabled = bool(persisted.get(CONF_ENABLED, self._enabled))
        self._last_action = persisted.get("last_action", self._last_action)
        self._degraded_reason = persisted.get("degraded_reason")
        self._uncertain_quarter = bool(persisted.get("uncertain_quarter", False))
        self._shed_stack = [
            entity_id
            for entity_id in persisted.get("shed_stack", [])
            if entity_id in {load.entity_id for load in self._runtime_config.loads}
        ]
        self._external_overrides = set(persisted.get("external_overrides", []))

        self._monthly_peak_kw = float(persisted.get("monthly_peak_kw", 0.0))
        peak_ts = persisted.get("monthly_peak_timestamp")
        self._monthly_peak_ts = (
            datetime.fromtimestamp(peak_ts, tz=dt_util.UTC) if peak_ts else None
        )

        persisted_month = persisted.get("month_key")
        if persisted_month != self._month_key:
            self._monthly_peak_kw = 0.0
            self._monthly_peak_ts = None

        for entity_id, ts in persisted.get("last_shed_at", {}).items():
            if entity_id in {load.entity_id for load in self._runtime_config.loads}:
                self._last_shed_at[entity_id] = datetime.fromtimestamp(ts, tz=dt_util.UTC)
        for entity_id, ts in persisted.get("last_restore_at", {}).items():
            if entity_id in {load.entity_id for load in self._runtime_config.loads}:
                self._last_restore_at[entity_id] = datetime.fromtimestamp(ts, tz=dt_util.UTC)
        for entity_id, ts in persisted.get("override_backoff_until", {}).items():
            if entity_id in {load.entity_id for load in self._runtime_config.loads}:
                self._override_backoff_until[entity_id] = datetime.fromtimestamp(
                    ts, tz=dt_util.UTC
                )

        for entity_id, samples in persisted.get("load_samples", {}).items():
            if entity_id in self._load_stats:
                self._load_stats[entity_id] = RollingLoadStats(samples=samples)

        power_ts = persisted.get("power_last_reported_ts")
        if power_ts is not None:
            self._power_last_reported_at = datetime.fromtimestamp(power_ts, tz=dt_util.UTC)
        self._power_last_reported_kw = persisted.get("power_last_reported_kw")

        persisted_quarter_key = persisted.get("quarter_start")
        current_quarter_key = (
            self._quarter_start_local.isoformat() if self._quarter_start_local else None
        )
        if persisted_quarter_key == current_quarter_key:
            self._energy_at_quarter_start_kwh = float(
                persisted.get("energy_at_quarter_start_kwh", 0.0)
            )
        else:
            self._initialize_baseline_from_current_energy(uncertain=True)
            self._uncertain_quarter = True

    def _seed_samples_from_current_states(self) -> None:
        """Seed in-memory energy and power samples from current states."""
        now = dt_util.utcnow()
        for entity_id in self._runtime_config.energy_entity_ids:
            state = self.hass.states.get(entity_id)
            value = energy_state_to_kwh(state)
            if value is None:
                continue
            self._append_energy_sample(entity_id, now, value)
        power_state = self.hass.states.get(self._runtime_config.power_sensor)
        power_kw = power_state_to_kw(power_state)
        if power_kw is not None:
            self._power_last_reported_kw = max(0.0, power_kw)
            self._power_last_reported_at = now

    def _initialize_baseline_from_current_energy(self, uncertain: bool) -> None:
        energy_now = self._current_energy_total_kwh()
        self._energy_at_quarter_start_kwh = energy_now if energy_now is not None else 0.0
        self._uncertain_quarter = uncertain

    def _register_listeners(self) -> None:
        tracked_entities = {
            self._runtime_config.power_sensor,
            *self._runtime_config.energy_entity_ids,
            *[load.entity_id for load in self._runtime_config.loads],
            *[
                load.power_sensor
                for load in self._runtime_config.loads
                if load.power_sensor is not None
            ],
        }
        self._unsubscribers.append(
            async_track_state_change_event(
                self.hass,
                tracked_entities,
                self._async_handle_state_changed,
            )
        )

        # Same-value telemetry support: keep power freshness based on reported updates.
        self._unsubscribers.append(
            async_track_state_report_event(
                self.hass,
                {self._runtime_config.power_sensor, *self._runtime_config.energy_entity_ids},
                self._async_handle_state_reported,
            )
        )

        self._unsubscribers.append(
            async_track_utc_time_change(
                self.hass,
                self._async_handle_quarter_boundary,
                minute="/15",
                second=0,
            )
        )

    async def _async_handle_state_changed(
        self, event: Event[EventStateChangedData]
    ) -> None:
        entity_id = event.data["entity_id"]
        new_state = event.data.get("new_state")
        now = dt_util.utcnow()

        if entity_id == self._runtime_config.power_sensor:
            power_kw = power_state_to_kw(new_state)
            if power_kw is not None:
                self._power_last_reported_kw = max(0.0, power_kw)
                self._power_last_reported_at = now
            return

        if entity_id in self._runtime_config.energy_entity_ids:
            energy_kwh = energy_state_to_kwh(new_state)
            if energy_kwh is not None:
                self._append_energy_sample(entity_id, now, energy_kwh)
            return

        load_map = {load.entity_id: load for load in self._runtime_config.loads}
        if entity_id not in load_map:
            return

        pending = self._pending_service_actions.get(entity_id)
        if pending and now - pending[1] < timedelta(seconds=20):
            expected_state = pending[0]
            if new_state and new_state.state == expected_state:
                self._pending_service_actions.pop(entity_id, None)
                return

        if entity_id in self._shed_stack and new_state and new_state.state == STATE_ON:
            self._shed_stack = [item for item in self._shed_stack if item != entity_id]
            self._override_backoff_until[entity_id] = now + timedelta(
                seconds=self._runtime_config.override_backoff_seconds
            )
            self._external_overrides.add(entity_id)
            self._last_action = f"external override detected for {entity_id}"
            self.async_set_updated_data(None)

    async def _async_handle_state_reported(
        self, event: Event[EventStateReportedData]
    ) -> None:
        entity_id = event.data["entity_id"]
        report_ts = event.data["last_reported"].astimezone(dt_util.UTC)
        state = event.data["new_state"]

        if entity_id == self._runtime_config.power_sensor:
            power_kw = power_state_to_kw(state)
            if power_kw is not None:
                self._power_last_reported_at = report_ts
                self._power_last_reported_kw = max(0.0, power_kw)
            return

        if entity_id in self._runtime_config.energy_entity_ids:
            energy_kwh = energy_state_to_kwh(state)
            if energy_kwh is not None:
                self._append_energy_sample(entity_id, report_ts, energy_kwh)

    async def _async_handle_quarter_boundary(self, now: datetime) -> None:
        now_local = now.astimezone(dt_util.get_time_zone("Europe/Brussels"))
        boundary = quarter_start(now_local)
        if self._quarter_start_local and boundary <= self._quarter_start_local:
            return

        boundary_energy = self._latest_energy_total_before(boundary)
        if boundary_energy is None:
            boundary_energy = self._current_energy_total_kwh()

        # Detect month rollover BEFORE updating the running monthly peak.
        # The completed quarter belongs to the old month; if the month changes we
        # reset the peak for the new month and do NOT carry over the old value.
        is_month_rollover = self._month_key != month_key(boundary)
        if is_month_rollover:
            self._month_key = month_key(boundary)
            self._monthly_peak_kw = 0.0
            self._monthly_peak_ts = None

        # Only update the running monthly peak when the completed quarter belongs
        # to the current (non-rolled-over) month.
        if (
            not is_month_rollover
            and boundary_energy is not None
            and self._energy_at_quarter_start_kwh is not None
            and self._quarter_start_local is not None
        ):
            completed_avg_kw = max(
                0.0, (boundary_energy - self._energy_at_quarter_start_kwh) * 4
            )
            if completed_avg_kw > self._monthly_peak_kw:
                self._monthly_peak_kw = completed_avg_kw
                self._monthly_peak_ts = now.astimezone(dt_util.UTC)

        new_baseline = self._latest_energy_total_before(boundary)
        if new_baseline is None:
            new_baseline = self._current_energy_total_kwh()
            self._uncertain_quarter = True
        else:
            self._uncertain_quarter = False

        self._quarter_start_local = boundary
        self._energy_at_quarter_start_kwh = new_baseline if new_baseline is not None else 0.0
        self._last_action = "quarter boundary baseline captured"
        await self._async_save_state()
        self.async_set_updated_data(None)

    async def _async_update_data(self) -> None:
        now = dt_util.utcnow()
        now_local = now.astimezone(dt_util.get_time_zone("Europe/Brussels"))

        # Handle missed boundaries while HA was busy.
        current_quarter = quarter_start(now_local)
        if self._quarter_start_local and current_quarter > self._quarter_start_local:
            await self._async_handle_quarter_boundary(now)

        energy_now = self._current_energy_total_kwh()
        if energy_now is None or self._energy_at_quarter_start_kwh is None:
            self._projected_avg_kw = None
            self._headroom_kw = None
            self._degraded_reason = "energy_unavailable"
            await self._async_save_state()
            return

        raw_used_kwh = energy_now - self._energy_at_quarter_start_kwh
        if raw_used_kwh < 0:
            # Backward jump: meter reset or Fluvius correction.
            _LOGGER.warning(
                "Backward energy jump detected (%.3f kWh); marking quarter uncertain",
                raw_used_kwh,
            )
            self._uncertain_quarter = True
            used_kwh = 0.0
        elif raw_used_kwh > MAX_PLAUSIBLE_QUARTER_KWH:
            # Forward jump larger than any realistic 15-minute consumption.
            _LOGGER.warning(
                "Suspicious forward energy jump (%.3f kWh > %.1f kWh); marking quarter uncertain",
                raw_used_kwh,
                MAX_PLAUSIBLE_QUARTER_KWH,
            )
            self._uncertain_quarter = True
            used_kwh = raw_used_kwh
        else:
            used_kwh = raw_used_kwh
        elapsed_seconds, remaining_seconds = quarter_elapsed_and_remaining_seconds(now_local)

        live_state = self.hass.states.get(self._runtime_config.power_sensor)
        live_kw = power_state_to_kw(live_state)
        if live_kw is not None:
            live_kw = max(0.0, live_kw)

        observed_avg_kw = (used_kwh / (elapsed_seconds / 3600)) if elapsed_seconds > 0 else 0.0

        degraded_reason = self._compute_degraded_reason(now, live_kw, observed_avg_kw)
        self._degraded_reason = degraded_reason
        projection_live_kw = observed_avg_kw if live_kw is None else live_kw
        projection = build_projection(
            used_kwh=used_kwh,
            live_kw=projection_live_kw,
            elapsed_seconds=elapsed_seconds,
            remaining_seconds=remaining_seconds,
        )

        self._projected_avg_kw = projection.projected_avg_kw
        self._headroom_kw = self._runtime_config.target_kw - projection.projected_avg_kw
        self._escalation_active = (
            remaining_seconds <= self._runtime_config.escalation_window_seconds
        )

        self._capture_load_power_samples()

        if self._enabled and self._can_run_control(now):
            if projection.projected_avg_kw > self._runtime_config.target_kw:
                await self._async_run_shed_cycle(
                    now=now,
                    projection=projection,
                    remaining_seconds=remaining_seconds,
                )
            else:
                await self._async_run_restore_cycle(
                    now=now,
                    projection=projection,
                    remaining_seconds=remaining_seconds,
                )
            self._last_control_run_at = now

        await self._async_save_state()

    def _can_run_control(self, now: datetime) -> bool:
        if self._last_control_run_at is None:
            return True
        interval_seconds = (
            self._runtime_config.escalation_interval_seconds
            if self._escalation_active
            else self._runtime_config.normal_interval_seconds
        )
        return (now - self._last_control_run_at) >= timedelta(seconds=interval_seconds)

    async def _async_run_shed_cycle(
        self,
        *,
        now: datetime,
        projection,
        remaining_seconds: int,
    ) -> None:
        candidates: list[ShedCandidate] = []
        for load in self._runtime_config.loads:
            if load.entity_id in self._shed_stack:
                continue
            state = self.hass.states.get(load.entity_id)
            if state is None or state.state != STATE_ON:
                continue

            # Respect override backoff: never re-shed a load the user manually
            # turned back on until the backoff window has expired.
            backoff_until = self._override_backoff_until.get(load.entity_id)
            if backoff_until and now < backoff_until:
                continue

            blocked_by_min_on_time = False
            last_restore = self._last_restore_at.get(load.entity_id)
            if (
                last_restore is not None
                and (now - last_restore) < timedelta(seconds=load.min_on_time_seconds)
                and not self._escalation_active
            ):
                blocked_by_min_on_time = True

            candidates.append(
                ShedCandidate(
                    entity_id=load.entity_id,
                    priority=load.priority,
                    expected_kw=self._resolve_expected_kw(load),
                    blocked_by_min_on_time=blocked_by_min_on_time,
                )
            )

        planned_sheds = select_shed_plan(
            projected_avg_kw=projection.projected_avg_kw,
            target_kw=self._runtime_config.target_kw,
            used_kwh=projection.used_kwh,
            live_kw=projection.live_kw,
            remaining_seconds=remaining_seconds,
            is_escalation=self._escalation_active,
            candidates=candidates,
        )

        if not planned_sheds:
            self._last_action = "target exceeded but no shed candidate available"
            return

        for entity_id in planned_sheds:
            await self._async_call_load_service(entity_id, turn_on=False)
            if entity_id not in self._shed_stack:
                self._shed_stack.append(entity_id)
            self._last_shed_at[entity_id] = now
            self._external_overrides.discard(entity_id)

        self._last_action = (
            f"shed {len(planned_sheds)} load(s): {', '.join(planned_sheds)}"
        )

    async def _async_run_restore_cycle(
        self,
        *,
        now: datetime,
        projection,
        remaining_seconds: int,
    ) -> None:
        if not self._shed_stack:
            return

        load_map = {load.entity_id: load for load in self._runtime_config.loads}
        restore_candidates: dict[str, RestoreCandidate] = {}
        for entity_id in self._shed_stack:
            load = load_map.get(entity_id)
            if load is None:
                continue
            blocked_by_cooldown = False
            last_shed = self._last_shed_at.get(entity_id)
            if last_shed and (now - last_shed) < timedelta(seconds=load.cooldown_seconds):
                blocked_by_cooldown = True
            backoff_until = self._override_backoff_until.get(entity_id)
            blocked_by_backoff = bool(backoff_until and now < backoff_until)
            restore_candidates[entity_id] = RestoreCandidate(
                entity_id=entity_id,
                expected_kw=self._resolve_expected_kw(load),
                blocked_by_cooldown=blocked_by_cooldown,
                blocked_by_backoff=blocked_by_backoff,
            )

        restore_entity = select_restore_candidate(
            target_kw=self._runtime_config.target_kw,
            used_kwh=projection.used_kwh,
            live_kw=projection.live_kw,
            remaining_seconds=remaining_seconds,
            degraded=self._degraded_reason is not None,
            shed_stack=self._shed_stack,
            restore_candidates=restore_candidates,
            now=now,
        )
        if not restore_entity:
            if self._degraded_reason is not None:
                self._last_action = "restore frozen due to degraded telemetry"
            return

        await self._async_call_load_service(restore_entity, turn_on=True)
        self._shed_stack = [item for item in self._shed_stack if item != restore_entity]
        self._last_restore_at[restore_entity] = now
        self._last_action = f"restored {restore_entity}"

    async def _async_call_load_service(self, entity_id: str, *, turn_on: bool) -> None:
        domain = entity_id.split(".", 1)[0]
        service = SERVICE_TURN_ON if turn_on else SERVICE_TURN_OFF
        expected_state = STATE_ON if turn_on else STATE_OFF
        self._pending_service_actions[entity_id] = (expected_state, dt_util.utcnow())
        await self.hass.services.async_call(
            domain,
            service,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

    def _resolve_expected_kw(self, load: LoadConfig) -> float:
        sensor_kw: float | None = None
        if load.power_sensor:
            sensor_kw = power_state_to_kw(self.hass.states.get(load.power_sensor))
            if sensor_kw is not None:
                sensor_kw = max(0.0, sensor_kw)

        stats = self._load_stats.setdefault(load.entity_id, RollingLoadStats())
        stats_p90 = stats.p90()
        return resolve_expected_load_kw(
            manual_expected_kw=load.manual_expected_kw,
            live_sensor_kw=sensor_kw,
            stats_p90_kw=stats_p90,
        )

    def _capture_load_power_samples(self) -> None:
        for load in self._runtime_config.loads:
            if not load.power_sensor:
                continue
            load_state = self.hass.states.get(load.entity_id)
            if load_state is None or load_state.state != STATE_ON:
                continue
            sensor_kw = power_state_to_kw(self.hass.states.get(load.power_sensor))
            if sensor_kw is None:
                continue
            self._load_stats.setdefault(load.entity_id, RollingLoadStats()).add_sample(
                max(0.0, sensor_kw)
            )

    def _compute_degraded_reason(
        self,
        now: datetime,
        live_kw: float | None,
        observed_avg_kw: float,
    ) -> str | None:
        if live_kw is None:
            return "power_unavailable"
        if self._power_last_reported_at is None:
            return "power_report_missing"

        silence = (now - self._power_last_reported_at).total_seconds()
        if silence <= self._runtime_config.telemetry_silence_seconds:
            return None

        if telemetry_conflict(
            live_kw=live_kw,
            observed_avg_kw=observed_avg_kw,
            conflict_abs_kw=self._runtime_config.telemetry_conflict_abs_kw,
            conflict_rel=self._runtime_config.telemetry_conflict_rel,
        ):
            return "telemetry_conflict"
        return None

    def _append_energy_sample(self, entity_id: str, when: datetime, value_kwh: float) -> None:
        samples = self._energy_samples.setdefault(entity_id, deque(maxlen=64))
        samples.append((when, value_kwh))

    def _current_energy_total_kwh(self) -> float | None:
        if self._runtime_config.energy_mode == ENERGY_MODE_TOTAL:
            return energy_state_to_kwh(self.hass.states.get(self._runtime_config.energy_sensor))
        if not (
            self._runtime_config.energy_sensor_day
            and self._runtime_config.energy_sensor_night
        ):
            return None
        day = energy_state_to_kwh(self.hass.states.get(self._runtime_config.energy_sensor_day))
        night = energy_state_to_kwh(
            self.hass.states.get(self._runtime_config.energy_sensor_night)
        )
        if day is None or night is None:
            return None
        return day + night

    def _latest_energy_total_before(self, when_local: datetime) -> float | None:
        when_utc = when_local.astimezone(dt_util.UTC)
        if self._runtime_config.energy_mode == ENERGY_MODE_TOTAL:
            if not self._runtime_config.energy_sensor:
                return None
            sample = self._latest_sample_before(self._runtime_config.energy_sensor, when_utc)
            return sample[1] if sample else None

        if not (
            self._runtime_config.energy_sensor_day
            and self._runtime_config.energy_sensor_night
        ):
            return None

        day_sample = self._latest_sample_before(
            self._runtime_config.energy_sensor_day, when_utc
        )
        night_sample = self._latest_sample_before(
            self._runtime_config.energy_sensor_night, when_utc
        )
        if not day_sample or not night_sample:
            return None
        return day_sample[1] + night_sample[1]

    def _latest_sample_before(
        self, entity_id: str, when_utc: datetime
    ) -> tuple[datetime, float] | None:
        samples = self._energy_samples.get(entity_id)
        if not samples:
            return None
        for timestamp, value in reversed(samples):
            if timestamp <= when_utc:
                return timestamp, value
        return None

    async def _async_save_state(self) -> None:
        payload: dict[str, Any] = {
            "quarter_start": self._quarter_start_local.isoformat()
            if self._quarter_start_local
            else None,
            "energy_at_quarter_start_kwh": self._energy_at_quarter_start_kwh,
            "shed_stack": self._shed_stack,
            "last_shed_at": {
                entity_id: timestamp.timestamp()
                for entity_id, timestamp in self._last_shed_at.items()
            },
            "last_restore_at": {
                entity_id: timestamp.timestamp()
                for entity_id, timestamp in self._last_restore_at.items()
            },
            "override_backoff_until": {
                entity_id: timestamp.timestamp()
                for entity_id, timestamp in self._override_backoff_until.items()
            },
            "load_samples": {
                entity_id: stats.as_list()
                for entity_id, stats in self._load_stats.items()
            },
            "monthly_peak_kw": self._monthly_peak_kw,
            "monthly_peak_timestamp": self._monthly_peak_ts.timestamp()
            if self._monthly_peak_ts
            else None,
            "month_key": self._month_key,
            "uncertain_quarter": self._uncertain_quarter,
            "enabled": self._enabled,
            "last_action": self._last_action,
            "degraded_reason": self._degraded_reason,
            "external_overrides": sorted(self._external_overrides),
            "power_last_reported_ts": self._power_last_reported_at.timestamp()
            if self._power_last_reported_at
            else None,
            "power_last_reported_kw": self._power_last_reported_kw,
        }
        await self._storage.async_save(payload)

    def extra_state_attributes(self) -> dict[str, Any]:
        """Extra state attributes shared by diagnostics."""
        return {
            ATTR_DEGRADED_REASON: self._degraded_reason,
            ATTR_UNCERTAIN_QUARTER: self._uncertain_quarter,
            "external_overrides": sorted(self._external_overrides),
            "target_kw": self._runtime_config.target_kw,
        }
