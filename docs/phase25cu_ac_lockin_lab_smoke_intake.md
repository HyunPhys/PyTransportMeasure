# Phase 25cu: AC Lock-In Lab Smoke Intake

This phase adds a post-run acceptance gate for the conservative Keithley 2450 +
SR860 AC lock-in hardware smoke path.

## Command

```powershell
ptm ac-lockin-lab-smoke-intake data\raw\<run> --min-points 5 --min-abs-lockin-r-v <low> --max-abs-lockin-r-v <high> --json-output docs\ac_lockin_lab_smoke_intake.json
```

## What It Checks

- `metadata.json` belongs to `measurement_type: ac_lockin_sweep`
- the run completed and `points_written` matches `points.csv`
- Keithley source NPLC, voltage range, current range, and compliance were saved
- Keithley source configuration readback exists and matched the requested setup
- SR860 setting readback was available and matched the recipe
- lock-in `R` values exist for every point
- optional absolute lock-in `R` bounds pass
- source output-off and zero-before-off cleanup succeeded

## Hardware Policy

This command does not touch hardware. It is a saved-run gate for deciding
whether a lab smoke result is clean enough to broaden AC measurements or move
toward Hall-bar lock-in workflows.

For real hardware smoke, keep the SR860 front panel in sync with the recipe
because PyTransportMeasure still reads and verifies SR860 settings rather than
configuring them automatically.
