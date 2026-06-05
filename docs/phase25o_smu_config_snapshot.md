# Phase 25o: SMU Configuration Snapshot

## Goal

Make Keithley source/measure configuration traceable across measurement
methods. Every active runner now builds `SMUVoltageSourceConfig` through one
shared helper and saves the exact intended settings in `metadata.json`.

## Snapshot Fields

Each snapshot records:

- `current_compliance_a`
- `voltage_range_v`
- `current_range_a`
- `terminal`
- `nplc`

The snapshot is saved before hardware output is enabled, and is preserved for
completed, interrupted, and partial runs.

## Metadata Keys

- Drain I-V: `configured_smu`
- Single-gate DC: `configured_drain_smu`, `configured_gate_smu`
- Dual-gate DC: `configured_drain_smu`, `configured_gate1_smu`,
  `configured_gate2_smu`
- AC lock-in: `configured_source_smu`
- Dual-gate lock-in and active-gate smoke: `configured_gate1_smu`,
  `configured_gate2_smu`
- Pulse dry-run/future pulse hardware path: `configured_source_smu`

## Why This Matters

For Hall-bar graphene work, many runs will involve multiple Keithleys and an
SR860. The recipe snapshot already stores user intent, but this snapshot records
the normalized config object passed into the instrument layer. That gives a
single place to audit NPLC, compliance, ranges, and terminal selection after a
run, including failed or partial runs.

Future Keithley parameters such as remote-sense mode, auto-zero, source delay,
or hardware averaging should be added to the shared config helper before
method-specific runners duplicate them.
