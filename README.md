# PeakShavr

PeakShavr is a Home Assistant custom integration for Belgian quarter-hour peak control (`capaciteitstarief` use case). It projects the end-of-quarter average, sheds configured loads by priority, and restores them when the same projection says it is safe.

> **Important:** PeakShavr exposes an **estimated** monthly peak from Home Assistant data. Billing is based on the grid operator meter, not this estimate.

## Scope (v1)

- Supports managed load entities in:
  - `switch`
  - `input_boolean` (proxy pattern)
- Requires:
  - live grid power sensor (`W` or `kW`)
  - cumulative import energy (`kWh`, or day/night split sensors)
- Uses:
  - one-load-per-pass shedding in normal mode
  - multi-load shedding in last 120 seconds of quarter (escalation)
  - restore freeze during degraded telemetry
  - rolling per-load p90 expected draw (or manual expected kW)

## Home Assistant requirements

- Home Assistant `2026.1.0` or newer
- A power sensor and energy sensor(s) with valid metadata:
  - power: numeric `W` or `kW`
  - energy: numeric `Wh` / `kWh` / `MWh` with `state_class` `total` or `total_increasing`

## Install with HACS

1. Add this repository as a custom repository in HACS (`Integration` type).
2. Install **PeakShavr**.
3. Restart Home Assistant.
4. Add the integration from **Settings → Devices & Services**.

## Configuration model

### Initial setup

- Select live power sensor.
- Select energy source mode:
  - single cumulative sensor, or
  - split day/night cumulative sensors.
- Set target peak (`kW`).

### Options flow

- Edit global settings (target, telemetry thresholds, control intervals).
- Add/edit/remove managed loads.
- Per-load configuration:
  - priority (lower sheds first),
  - expected-power source (`power_sensor` or manual expected `kW`),
  - minimum draw threshold (`kW`) to allow shedding in normal mode,
  - cooldown and minimum on-time.

## Exposed entities

- `sensor.*projected_avg_kw` — projected quarter-end average (`kW`)
- `sensor.*headroom_kw` — target minus projected (`kW`)
- `sensor.*monthly_peak_kw` — estimated monthly peak (`kW`)
- `sensor.*active_shed_count` — count of currently shed loads
- `sensor.*last_action` — last controller decision
- `binary_sensor.*escalation` — whether escalation mode is active
- `switch.*enabled` — enable/disable control loop

## Degraded telemetry behavior

An unchanged power value is not stale by itself. PeakShavr relies on Home Assistant reported-state updates and only marks telemetry degraded when:

- power becomes unavailable, or
- report silence exceeds threshold and power conflicts with energy-derived demand.

When degraded, PeakShavr **freezes restores** and keeps shedding behavior available.

## Development

Run tests:

```bash
python3 -m pytest -q
```

## License

GNU General Public License v3.0 only (GPL-3.0). See `LICENSE`.
