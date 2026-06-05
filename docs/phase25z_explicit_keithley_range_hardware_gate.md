# Phase 25z: Explicit Keithley Range Hardware Gate

This phase broadens the hardware-output measurement-parameter guard from NPLC
alone to the core Keithley 2450 source/sense settings.

## Scope

Before any guarded CLI path enables Keithley output, every active Keithley 2450
block must now declare:

- `voltage_range_v`
- `current_range_a`
- `nplc`

Dry-runs remain available without these values so recipe shape, artifact
writing, plotting, and reports can still be tested before the hardware recipe is
fully finalized.

## Guarded Paths

The broader SMU parameter guard applies to:

- Drain I-V hardware runs
- Single-gate hardware runs
- AC lock-in hardware runs
- Dual-gate lock-in active-gate smoke
- Dual-gate lock-in active sweeps

The readout-only dual-gate lock-in SR860 smoke path still uses the older NPLC
check because it does not enable gate outputs.

## Why

For Hall-bar graphene measurements, range settings are not bookkeeping. Current
range choices affect leakage checks, noise floor, speed, and whether instrument
autorange can change conditions mid-run. Hardware recipes should therefore
state the intended ranges explicitly before output is enabled.

## Example

```yaml
gate1_instrument:
  id: keithley_2450
  address: GPIB0::2::INSTR
  voltage_range_v: 0.2
  current_range_a: 1.0e-9
  nplc: 1.0
```

If a required value is missing, the CLI exits before constructing active
hardware instruments and prints a measurement-parameter failure such as:

```text
Measurement parameter check failed:
- gate1.current_range_a: gate1 Keithley 2450 hardware runs require explicit current range
Set the missing value in the recipe before enabling hardware output.
```

## Lab Checklist

- Confirm every active Keithley block declares voltage range, current range, and
  NPLC before running hardware.
- Confirm dry-run still works with incomplete SMU parameter blocks.
- Confirm hardware commands fail before output when one of the required values
  is removed.
- Confirm `metadata.json` still records the normalized `configured_*_smu`
  snapshots and readback checks.
