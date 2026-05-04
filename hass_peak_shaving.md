# Belgian digital meter peak-limiting automation — revised plan (v2)

## Problem

Build a HACS-installable Home Assistant custom integration that limits the monthly quarter-hour peak for the Belgian `capaciteitstarief`. The controller sheds loads in a user-defined priority order when projected demand exceeds a target, and restores them one-by-one when it can prove it is safe to do so — without a manual "restore margin" knob.

## Research summary

### What metric matters in Belgium

- The relevant metric is the **highest clock-aligned 15-minute average power in a month**.
- This is **not** a rolling window. Quarter boundaries are fixed at `00, 15, 30, 45`.
- The correct control target is the **projected end-of-quarter average power**, not instantaneous wattage.
- The Belgian "capaciteitstarief" (capacity tariff) is managed by **Fluvius** (grid operator) and regulated by the **VREG**.
- Your monthly distribution charge is based on your **highest monthly peak** (the worst single quarter-hour average of the month).
- Reference: https://nathan.gs/2022/11/27/flanders-capacity-electricity-tariffs-in-home-assistant/

### Existing reusable component (reference only)

- **Power Load Balancer** (`chicco-carone/Power-Load-Balancer`, v1.1.2) handles instantaneous overload balancing. It is useful reference material for priority-based shed/restore patterns, but is **not** designed for quarter-hour peak prediction. It optimizes against real-time watts, not projected quarter-end averages.

---

## Architecture

### Source sensors

| Role | Requirement | Purpose |
|------|-------------|---------|
| **Live grid power** | **Required** | Primary control signal. Needed for responsive projection and timely shedding. |
| **Cumulative energy import** | **Required** | Quarter accounting: the definitive measure of energy consumed in the current quarter. |

Both sensors are selected by the user in the config flow. The integration validates that:
- the energy sensor is monotonically increasing (`total` / `total_increasing` state class),
- the power sensor is a numeric sensor reporting W or kW.

If users have split tariff sensors (day/night), the integration should either require a total-import sensor or sum tariffs internally.

### Projection math (explicit)

```
q_start          = most recent local quarter boundary (floored to :00/:15/:30/:45)
elapsed_s        = now - q_start                               (seconds into quarter)
remaining_s      = 900 - elapsed_s                             (seconds left)
used_kwh         = energy_now - energy_at_q_start              (energy consumed so far)
live_kw          = current grid power / 1000                   (if W) or as-is (if kW)

projected_kwh    = used_kwh + (live_kw * remaining_s / 3600)
projected_avg_kw = projected_kwh / 0.25                        (= projected_kwh * 4)
```

Key rules:
- `energy_at_q_start` is captured at each quarter boundary and persisted.
- If `live_kw` is stale (>60 s since last update), degrade to `projected_avg_kw = used_kwh / (elapsed_s / 3600)` and log a warning.
- Negative energy deltas are ignored (meter reset / reconnect).
- The `live_kw` input should be smoothed (short exponential moving average, τ ≈ 30 s) to reduce noise without adding too much lag.

### Restore logic — calculated, not manual

There is **no static "restore margin" setting**. Instead, the restore decision uses the same projection math with the candidate load's power added:

```
load_expected_kw   = conservative estimate of load X's power draw
                     (default: 90th percentile from its power sensor history,
                      configurable per load: latest / avg / median / p90 / max)

projected_with_load = (used_kwh + (live_kw + load_expected_kw) * remaining_s / 3600) * 4

restore_allowed     = projected_with_load <= target_kw
```

Why this works:
- Early in the quarter (`remaining_s` is large), adding a load has a big projected impact → conservative.
- Late in the quarter (`remaining_s` is small), adding a load barely moves the projection → more permissive.
- No manual knob needed: the math naturally adapts to time-in-quarter.
- Using a conservative power statistic (p90/max) accounts for startup surges without requiring a separate margin.

### Shed logic — with escalation

**Normal mode** (> 120 s remaining in quarter):
- Controller runs every **30 seconds**.
- Sheds **one load per cycle** in priority order when `projected_avg_kw > target_kw`.
- After shedding, waits for sensor feedback before deciding on the next load (settle time).

**Escalation mode** (≤ 120 s remaining in quarter):
- Controller runs every **10 seconds**.
- May shed **multiple loads in a single pass** until `projected_avg_kw <= target_kw`.
- This prevents the scenario where one-load-at-a-time is too slow to save a late-quarter spike.

### Anti-chatter protection

- **Per-load cooldown**: a load cannot be restored within 60 s of being shed (configurable).
- **Per-load minimum on-time**: a restored load cannot be re-shed within 60 s of restore (configurable).
- **External override detection**: if a shed load's state changes to "on" externally (user/automation), the controller removes it from its shed list and will not fight the override until the next quarter.

### Restart recovery

Persisted across HA restarts (via `hass.data` + `store` / JSON):
- current quarter start timestamp,
- energy baseline at quarter start,
- list of loads currently shed by the controller,
- last action timestamp per load,
- current month peak (highest completed quarter average this month),
- month peak timestamp.

On startup:
- If within the same quarter: restore state and resume control.
- If a new quarter has started since shutdown: reset quarter baseline, keep shed list but allow restore evaluation.
- If month has rolled over: reset monthly peak.

### Conflict handling

- If a load the controller shed is turned on externally, the controller detects the state change and **releases ownership** of that load for the current quarter.
- The controller never fights another automation or manual override.
- A diagnostic sensor exposes "externally overridden" loads.

---

## v1 scope (cut to achievable)

### In scope
- `switch` and `input_boolean` proxy entities.
- Live grid power + cumulative energy as required inputs.
- Projection, shed, escalation, restore with calculated safety.
- Per-load power sensor pairing.
- Integer priority per load (simple ordering).
- Persistence and restart recovery.
- Monthly peak tracking.
- Enable/disable switch.
- Diagnostic sensors (projection, headroom, monthly peak, active shed level, last action).
- HACS packaging.

### Deferred to v1.1+
- **Climate entities** (slow response, device-specific offset semantics — better as a proven add-on).
- **Continuous throttling** (number-based EV current limiting, etc.).
- **Built-in proxy action handling** (v1 only toggles the boolean; user provides automations).
- **Selectable restore statistic in the UI** — v1 defaults to p90; making it configurable is a settings-flow enhancement.
- **Multi-zone / multi-meter** support.

### Why climate is deferred
- Offset-based temperature control is slow: floor heating or heat pumps may not reduce power within the same quarter.
- Device semantics vary wildly (dual setpoint, min/max clamping, mode conflicts).
- It gives a false sense of protection: a -5 C offset does not guarantee immediate kW reduction.
- **Recommendation**: use an `input_boolean` proxy for climate loads in v1, and trigger a separate user automation that handles the specifics of your heating system.

---

## Configuration model

### Config flow (initial setup)
1. Select **live grid power sensor** (required, W or kW).
2. Select **cumulative energy import sensor** (required, kWh, total/total_increasing).
3. Set **target peak** (default: 3.0 kW).

### Options flow (add/edit loads)
- Add a controllable entity (`switch.*` or `input_boolean.*`).
- Pair it with its **power sensor**.
- Assign an **integer priority** (lower = shed first).
- Optionally set **cooldown** and **minimum on-time** overrides.
- Remove / reorder existing loads.

No YAML configuration path in v1. All configuration through the UI.

---

## Observability (exposed entities)

| Entity | Type | Description |
|--------|------|-------------|
| `sensor.peak_guard_projected_avg` | sensor (kW) | Projected quarter-end average power |
| `sensor.peak_guard_headroom` | sensor (kW) | target − projected (negative = over budget) |
| `sensor.peak_guard_monthly_peak` | sensor (kW) | Highest completed quarter average this month |
| `sensor.peak_guard_active_shed_count` | sensor | Number of loads currently shed |
| `sensor.peak_guard_last_action` | sensor | Human-readable last decision |
| `switch.peak_guard_enabled` | switch | Enable/disable the controller |
| `binary_sensor.peak_guard_escalation` | binary_sensor | Whether escalation mode is active |

---

## Testing strategy

### Unit tests (pytest)
- Quarter boundary math (including DST transitions in `Europe/Brussels`).
- Projection formula with various elapsed/remaining ratios.
- Shed priority ordering.
- Escalation trigger and multi-load shed.
- Restore decision with calculated headroom.
- Negative energy delta handling.
- Stale sensor detection.

### Integration tests
- HA restart mid-quarter with persisted state.
- External override detection.
- Config entry setup and options flow.
- Entity creation and state updates.

---

## Implementation phases

1. **Scaffold**: repository layout, manifest, hacs.json, translations, empty integration bootstrap.
2. **Config flow**: initial setup + options flow for load management.
3. **Projection engine**: quarter-aware math, baseline capture, persistence.
4. **Controller runtime**: periodic loop, shed logic, escalation mode.
5. **Restore engine**: calculated restore safety, cooldowns, override detection.
6. **Observability**: sensor/switch entities, diagnostics.
7. **Testing**: unit + integration tests for the hard parts.
8. **HACS packaging**: docs, screenshots, versioning, release.

---

## Confirmed design decisions (revised)

- **Source data**: live grid power (required) + cumulative energy import (required).
- **Implementation level**: HACS custom integration.
- **Restore logic**: calculated from projection math — no manual margin knob.
- **Restore safety statistic**: default p90 of load's power sensor history.
- **Target strategy**: fixed personal kW target, default 3 kW.
- **Configuration style**: UI only (config_flow + options_flow).
- **Control mode**: discrete on/off shedding only in v1.
- **Supported domains in v1**: `switch`, `input_boolean` proxy.
- **Climate**: deferred to v1.1 (use proxy in v1).
- **Priority model**: integer priority per load; lower = shed first.
- **Escalation**: multi-load shedding when ≤ 120 s remain in quarter.
- **Anti-chatter**: per-load cooldown (default 60 s) + minimum on-time (default 60 s).
- **Conflict handling**: external overrides are respected; controller releases ownership.
- **Persistence**: quarter baseline, shed state, monthly peak survive restarts.
- **Monthly peak**: tracked and exposed; resets on month boundary in local timezone.

---

## Key formulas reference

### Projection (current quarter-end average)
```python
from datetime import datetime, timezone
import zoneinfo

tz = zoneinfo.ZoneInfo("Europe/Brussels")
now = datetime.now(tz)
q_minute = (now.minute // 15) * 15
q_start = now.replace(minute=q_minute, second=0, microsecond=0)
elapsed_s = (now - q_start).total_seconds()
remaining_s = 900 - elapsed_s

used_kwh = energy_now - energy_at_q_start
live_kw = live_power_w / 1000  # if sensor reports W

projected_kwh = used_kwh + (live_kw * remaining_s / 3600)
projected_avg_kw = projected_kwh * 4  # divide by 0.25 h
```

### Shed decision
```python
should_shed = projected_avg_kw > target_kw
```

### Restore decision (for candidate load X)
```python
load_expected_kw = get_p90_power(load_x_power_sensor)  # from recorder history
projected_with_load = (used_kwh + (live_kw + load_expected_kw) * remaining_s / 3600) * 4
restore_allowed = projected_with_load <= target_kw
```

### Stale sensor fallback
```python
if seconds_since_last_power_update > 60:
    # Fallback: use only what we know for certain
    projected_avg_kw = (used_kwh / (elapsed_s / 3600)) if elapsed_s > 0 else 0
    log_warning("Live power sensor stale; projection degraded")
```

---

## Repository structure (target)

```
ha-peak-guard/
├── custom_components/
│   └── peak_guard/
│       ├── __init__.py          # Integration setup, platform loading
│       ├── config_flow.py       # Config flow + options flow
│       ├── const.py             # Constants, defaults, domain name
│       ├── coordinator.py       # DataUpdateCoordinator or custom controller
│       ├── projection.py        # Quarter-aware projection engine
│       ├── controller.py        # Shed/restore state machine
│       ├── store.py             # Persistence (JSON store)
│       ├── sensor.py            # Diagnostic sensor entities
│       ├── switch.py            # Enable/disable switch entity
│       ├── binary_sensor.py     # Escalation mode binary sensor
│       ├── manifest.json
│       ├── strings.json         # Translations
│       └── translations/
│           └── en.json
├── tests/
│   ├── conftest.py
│   ├── test_projection.py
│   ├── test_controller.py
│   ├── test_restore.py
│   ├── test_config_flow.py
│   └── test_persistence.py
├── hacs.json
├── README.md
├── LICENSE
└── .github/
    └── workflows/
        └── validate.yml         # HACS validation + pytest
```

---

## Edge cases to handle

1. **DST transition**: quarter boundaries must use local time (`Europe/Brussels`). Spring forward can create a 45-minute gap; fall back can create duplicate quarters. Use timezone-aware datetime throughout.
2. **Sensor unavailable on startup**: if either required sensor is unavailable, suspend control and expose a repair/diagnostic.
3. **Meter reconnect after gap**: if cumulative energy jumps (positive) unexpectedly, validate against live power × gap duration; if unreasonable, treat as meter reconnect and reset quarter baseline.
4. **All loads already shed**: if projected demand is still above target with no more loads to shed, log a warning and expose it in diagnostics — nothing more can be done.
5. **Quarter boundary race**: capture `energy_at_q_start` as close to the boundary as possible. Use `async_track_utc_time_change` aligned to :00/:15/:30/:45 for reliable boundary events.
6. **Month boundary**: reset monthly peak at `00:00` on the 1st of each month in local time.
7. **Entity removed from config**: if a load entity is removed while shed, the integration should not attempt to restore it (entity may no longer exist).
