# Phase 25ak: Keithley Measurement Parameter Audit

This phase tightens the measurement-parameter policy around Keithley 2450
hardware runs.

## Why

For Hall-bar graphene scans, the gate Keithleys may sit at many voltage points
for a long time. Missing or implicit Keithley settings can make two runs with
the same gate grid physically different. In particular, NPLC is not a cosmetic
option: it controls the current measurement integration time in power-line
cycles, trading speed for current averaging.

## Active Keithley Parameters

Every active Keithley 2450 source block should declare:

- `voltage_range_v`: explicit voltage source range.
- `current_range_a`: explicit measured-current range.
- `nplc`: current-measurement integration time in power-line cycles.
- `source_delay_s`: optional Keithley-side voltage source delay.

The CLI hardware guards already block active Keithley output when
`voltage_range_v`, `current_range_a`, or `nplc` is missing. Dry-runs remain
available so recipe shape and artifacts can be tested before lab execution.

## Code Policy

The required hardware parameters are centralized in
`pytransport.measurement_parameters.REQUIRED_KEITHLEY_HARDWARE_PARAMETERS`.
Each entry carries:

- parameter name,
- user-facing label,
- reason for the policy.

This keeps future additions such as auto-zero, remote sense, or measurement
filtering from becoming scattered one-off checks.

## Lab Checklist

- [ ] Confirm every active Keithley block has the intended `nplc`.
- [ ] Confirm the plan output shows the intended NPLC before hardware output.
- [ ] After a hardware run, inspect `configured_*_smu.nplc` in `metadata.json`.
- [ ] Inspect `configured_*_smu_readback.current_nplc` when readback is
  available.
- [ ] If the run is slow/noisy, adjust NPLC deliberately rather than leaving it
  implicit.

