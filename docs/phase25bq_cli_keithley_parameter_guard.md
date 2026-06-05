# Phase 25bq: CLI Keithley Parameter Guard

## Summary

This phase tightens the hardware-facing Drain I-V CLI path around Keithley 2450
measurement parameters.

The Keithley driver already supports current-measurement NPLC through:

```text
:SENS:CURR:NPLC <value>
```

and reads it back through:

```text
:SENS:CURR:NPLC?
```

The missing piece was a direct CLI regression test proving that `ptm run`
blocks a real hardware run before preflight or output setup if required
Keithley parameters are absent.

## Required Keithley Hardware Parameters

For active hardware output, every Keithley source block must explicitly declare:

- `nplc`: current integration time in power-line cycles.
- `voltage_range_v`: voltage source range.
- `current_range_a`: measured-current range.

Dry-runs may omit these fields so recipe shape and artifact flow can still be
tested without hardware.

## Why NPLC Matters

NPLC is not cosmetic. It changes the current integration time and therefore the
noise/speed tradeoff. For graphene Hall-bar scans, NPLC must stay fixed when
comparing repeated scans unless the lab deliberately changes it and records that
change in the recipe and notebook.

## Verification

- `ptm run <recipe>` blocks hardware when `instrument.nplc` is missing.
- `ptm run <recipe> --dry-run` still works with missing hardware-only
  parameters.
- `ptm run <recipe> --yes` passes explicit NPLC/range values into the shared
  SMU configuration before the Keithley driver is called.

## Lab Checklist

- [ ] Confirm every active Keithley block has `nplc`, `voltage_range_v`, and
      `current_range_a`.
- [ ] Confirm `ptm plan <recipe>` shows the intended NPLC before hardware run.
- [ ] Confirm `metadata.json` contains `configured_*_smu.nplc` after a run.
- [ ] Confirm `configured_*_smu_readback.current_nplc` matches the recipe when
      hardware readback is available.
