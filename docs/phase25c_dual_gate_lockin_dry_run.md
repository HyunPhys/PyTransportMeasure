# Phase 25c - Dual-Gate Lock-In Dry-Run Foundation

This phase adds the first dual-gate method aligned with the currently described
hardware set: two Keithley 2450 source meters for gate biases and one SR860
lock-in amplifier for source-drain readout.

## What Changed

- Added `DualGateLockInRecipe` with:
  - `gate1_instrument`
  - `gate2_instrument`
  - `lockin`
  - `gate1_sweep`
  - `gate2_sweep`
- Added `ptm dual-gate-lockin-plan`.
- Added dry-run-only `ptm dual-gate-lockin`.
- Added fake dual-gate lock-in readout that can depend on gate1, gate2, and a
  cross term.
- Added saved-run artifacts:
  - `points.csv`
  - `metadata.json`
  - `dual_gate_lockin_heatmap.svg`
  - `dual_gate_lockin_stats.csv`
  - `dual_gate_lockin_report.md`
- Registered `dual_gate_lockin_sweep` with the shared method registry.

## Current Hardware Policy

Hardware execution is blocked. This is intentional until the SR860 excitation,
input wiring, and two-gate Keithley safety preflight are explicit and tested.

## Commands

```powershell
ptm dual-gate-lockin-plan configs/recipes/dual_gate_lockin_dry_run.yaml
ptm dual-gate-lockin configs/recipes/dual_gate_lockin_dry_run.yaml --dry-run --summary --plot --report --gate-stats --fake-noise-std 0
```

## Next Step

Add dual-gate lock-in preflight:

- verify gate1 Keithley address
- verify gate2 Keithley address
- verify SR860 address
- require distinct resources
- print SR860 excitation/readout assumptions before output is enabled
