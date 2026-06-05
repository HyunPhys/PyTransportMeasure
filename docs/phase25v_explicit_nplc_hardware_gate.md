# Phase 25v: Explicit NPLC Hardware Gate

## Goal

Require explicit Keithley 2450 NPLC values before any CLI path enables hardware
output. Dry-runs remain allowed without NPLC so recipe shape and artifact flow
can still be tested.

## Why

NPLC controls the current-measurement integration time. For Hall-bar graphene
work, especially leakage checks and low-current gate sweeps, this is not a
cosmetic setting. A hardware run should not inherit an unknown front-panel or
reset default without the recipe saying so.

## Guarded Hardware Paths

The CLI now blocks missing NPLC before constructing active hardware instruments
for:

- Drain I-V hardware runs
- Single-gate hardware runs
- AC lock-in hardware runs
- Dual-gate lock-in active-gate smoke
- Dual-gate lock-in active sweeps

Read-only SR860 smoke and all dry-run paths remain available.

## Error

If NPLC is missing, the command exits before output can be enabled and prints a
message like:

```text
Measurement parameter check failed:
- source.nplc: source Keithley 2450 hardware runs require explicit NPLC
Set the missing value in the recipe before enabling hardware output.
```

## Recipe Example

```yaml
source_instrument:
  id: keithley_2450
  address: GPIB0::2::INSTR
  voltage_range_v: 0.02
  current_range_a: 1.0e-7
  nplc: 1.0
```

Use larger NPLC values for quieter low-current measurements when the slower
scan speed is acceptable.

Later policy note: Phase 25z extends this hardware-output guard to require
explicit Keithley `voltage_range_v` and `current_range_a` as well. NPLC remains
required, but it is now part of a broader SMU parameter readiness check.
