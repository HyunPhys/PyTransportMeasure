# Phase 25au: Hall Suite Aggregate Plan

This phase adds a hardware-free aggregate runbook for a Hall-bar dual-gate
lock-in suite.

## What Changed

- Added `ptm dual-gate-lockin-hall-suite-plan`.
- The command accepts longitudinal Vxx, `+B` Vxy, `-B` Vxy, and optional `0B`
  Vxy recipes.
- It runs the existing suite consistency audit first.
- If the suite is compatible, it prints:
  - Vxx/+B/-B/0B measurement order
  - hardware-free check, plan, and preflight commands
  - guarded hardware run command templates
  - Hall antisymmetry, zero-field correction, and mobility analysis commands
  - per-recipe plan snapshots
- If the suite is inconsistent, it prints the failure report and exits nonzero
  before showing hardware templates.

## Why It Matters

The Hall-bar workflow spans several related measurements. Keeping the suite plan
as a single command reduces the chance of running Vxx and Vxy recipes with
mismatched gate grids, Keithley settings, SR860 settings, safety presets, or
magnetic-field metadata.

This command does not touch VISA, Keithley outputs, or SR860 communication. It
is safe to run on the development machine before moving the recipe set to the
lab laptop.

## Usage

```powershell
ptm dual-gate-lockin-hall-suite-plan configs\recipes\<suite>\<prefix>_vxx.yaml configs\recipes\<suite>\<prefix>_vxy_plus_b.yaml configs\recipes\<suite>\<prefix>_vxy_minus_b.yaml --zero-field-recipe configs\recipes\<suite>\<prefix>_vxy_zero_b.yaml
```

Use `--preview-points <N>` to control how many planned points are shown in each
per-recipe plan snapshot.

## Verification

- `python -m pytest tests\test_hall_suite_template.py -q`
- `python -m pytransport.cli dual-gate-lockin-hall-suite-plan --help`
- `python -m pytest -q`
- `git diff --check`
