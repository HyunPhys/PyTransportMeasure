# Phase 25t: Voltage Command Tracking

## Goal

Record the last commanded voltage for every active SMU role. Partial and failed
runs should show which drain/gate/source setpoint was last requested before
cleanup.

## Metadata

Each role in `output_state` now includes:

- `voltage_command_count`
- `last_commanded_voltage_v`
- `last_voltage_command_error`
- `last_commanded_voltage_before_zero_v`

The final zero-before-off cleanup is also counted as a voltage command, so
`last_commanded_voltage_v` should usually be `0.0` after cleanup. Use
`last_commanded_voltage_before_zero_v` to inspect the last measurement setpoint
before cleanup began.

## Behavior

All runner-level voltage commands now pass through the output-state helper:

- Drain I-V drain/source sweep commands
- Single-gate drain and gate commands
- Dual-gate DC drain, gate1, and gate2 commands
- AC lock-in source bias commands
- Dual-gate lock-in gate1 and gate2 commands
- Active-gate smoke gate commands
- Pulse source pulse/base commands

If a voltage command fails, the error is recorded as
`last_voltage_command_error` and the runner handles the exception through the
normal partial-run metadata path.

## Hardware Use

For an interrupted Hall-bar scan, inspect `output_state`:

- `last_commanded_voltage_before_zero_v` shows the last non-cleanup setpoint.
- `last_commanded_voltage_v` should be `0.0` after successful cleanup.
- `voltage_command_count` helps distinguish a run that stopped before output
  from one that stopped after several gate points.
