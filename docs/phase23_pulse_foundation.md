# Phase 23 - Pulse Measurement Foundation

This phase promotes pulse measurement from an internal TODO into a supported
dry-run method family.

## Implemented

- Added `configs/recipes/pulse_dry_run.yaml`.
- Registered `pulse_measurement` in the method registry.
- Added `ptm pulse-plan`.
- Added dry-run-only `ptm pulse`.
- Added pulse CSV, metadata, recipe snapshot, safety snapshot, SVG plot, and
  Markdown report artifacts.
- Added generic saved-run dispatch for pulse summary, plot, report, inspect,
  run index, and campaign collection.
- Added pulse safety checks for the global safety preset and recipe-declared
  pulse limits.
- Added tests for recipe validation, plan formatting, dry-run artifacts,
  summary/plot/report, partial stop, and registry dispatch.

## Current User Commands

```powershell
ptm pulse-plan configs/recipes/pulse_dry_run.yaml
ptm pulse configs/recipes/pulse_dry_run.yaml --dry-run --summary --plot --report --progress --fake-resistance-ohm 1000000 --fake-noise-std-a 0
ptm inspect-run data\raw\<pulse_run_folder>
ptm summarize data\raw\<pulse_run_folder>
ptm plot data\raw\<pulse_run_folder>
ptm report data\raw\<pulse_run_folder>
```

## Hardware Policy

Pulse hardware output is intentionally blocked in this phase. Running `ptm
pulse <recipe>` without `--dry-run` prints the pulse plan and exits before any
instrument output is enabled.

The hardware implementation should only be enabled after:

- Keithley 2450 pulse-related SCPI commands are reviewed against the manual.
- A resistor-load smoke-test recipe is added.
- Output-off and partial-save behavior are tested around pulse-specific errors.
- Pulse timing limitations of the Python/VISA path are explicitly documented.

## Design Notes

Pulse measurement is its own method family. It is not a flag on Drain I-V.

The recipe owns:

- base voltage
- pulse voltage
- pulse width
- pulse period
- pulse count
- acquisition mode
- current compliance
- pulse-specific declared limits

The current acquisition mode is `pulse_end`, meaning one current sample is
recorded per pulse at the simulated pulse-high state.
