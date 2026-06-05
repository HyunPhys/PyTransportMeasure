# Phase 25g: Dual-Gate Lock-In Readout Smoke

This phase adds a safe hardware smoke command for the dual-gate lock-in path.

## Command

```powershell
ptm dual-gate-lockin-smoke configs/recipes/dual_gate_lockin_dry_run.yaml --samples 5 --interval-s 0.2 --progress
```

## Safety Boundary

The command runs the three-instrument dual-gate lock-in preflight first. If
preflight fails, no readout file is created.

When preflight passes, the command connects only to SR860 for readout. It reads
X/Y/R/theta using the current front-panel settings and saves:

- `lockin_smoke.csv`
- `metadata.json`
- recipe and safety snapshots

It does not configure Keithley source mode and does not enable gate outputs.

## Purpose

This is for checking SR860 signal path, front-panel settings, and Hall-bar
topology assumptions before any active gate sweep is enabled.

## Dry-Run

```powershell
ptm dual-gate-lockin-smoke configs/recipes/dual_gate_lockin_dry_run.yaml --dry-run --samples 5 --interval-s 0 --fake-lockin-r-v 0.000002 --fake-lockin-phase-deg 30 --fake-noise-std 0 --progress
```
