# Phase 50: GUI Scheme Drain I-V Overrides

## Goal

Extend the GUI Scheme Builder beyond simple step ordering by exposing common
Drain I-V recipe overrides per scheme step.

This lets a user reuse one base Drain I-V recipe while changing sweep conditions
for individual scheme steps.

## What Changed

- Added override fields to `GuiSchemeStepDraft`:
  - `measurement_suffix`
  - `sweep_start_v`
  - `sweep_stop_v`
  - `sweep_points`
  - `sweep_delay_s`
  - `sweep_current_compliance_a`
- Added override columns to the GUI Schemes step table:
  - `Suffix`
  - `Start V`
  - `Stop V`
  - `Points`
  - `Delay s`
  - `Compliance A`
- `Form -> Scheme YAML` now writes `overrides` for `drain_iv` rows when these
  fields are filled.
- `Scheme YAML -> Form` round-trips existing Drain I-V overrides back into the
  table.
- Scheme plan preview shows the expanded overridden recipe and the explicit
  override summary from the shared scheme core.

## Current Scope

Supported override target:

- `drain_iv` scheme steps.

Supported override fields:

- measurement suffix
- sweep start/stop voltage
- point count
- delay
- current compliance

Not yet included:

- single-gate overrides,
- AC lock-in/pulse scheme steps,
- matrix row generation UI,
- output directory and experiment metadata override UI.

## User Checklist

- Open `ptm-gui`.
- Open `Schemes`.
- In a `drain_iv` row, set:
  - `Suffix`: `_small`
  - `Start V`: `-0.05`
  - `Stop V`: `0.05`
  - `Points`: `5`
- Click `Form -> Scheme YAML`.
- Confirm the YAML contains:
  - `overrides:`
  - `measurement_suffix: _small`
  - `sweep:`
  - `start_v: -0.05`
  - `stop_v: 0.05`
  - `points: 5`
- Click `Check Scheme`.
- Click `Scheme Plan`.
- Confirm the plan shows the overridden sweep and an `Overrides` section.

