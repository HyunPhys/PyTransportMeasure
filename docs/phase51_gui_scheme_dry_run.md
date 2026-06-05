# Phase 51: GUI Scheme Dry-Run

## Goal

Let the desktop GUI execute a generated scheme as a dry-run and review the saved
scheme artifacts without leaving the app.

This connects the GUI Scheme Builder to the existing scheme summary/report
pipeline. Hardware scheme execution remains intentionally blocked until a
separate smoke-test phase.

## What Changed

- Added `GuiSchemeRunResult`.
- Added `run_gui_scheme_dry_run_text()`.
- The GUI scheme dry-run path supports:
  - direct Drain I-V steps,
  - direct single-gate steps,
  - nested batch steps containing Drain I-V recipes.
- Scheme dry-runs create:
  - `scheme_summary.json`,
  - `scheme_report.md`,
  - `scheme_runs.csv`,
  - `scheme_points.csv`,
  - `scheme_stats.csv`,
  - `scheme_overlay.svg` when plottable data exists.
- Added `Dry Run Scheme` to the `Schemes` workspace.
- Added `Result` and `Report` tabs in `Schemes`.
- Added buttons to open the saved scheme folder and scheme report.

## Design Notes

The GUI uses the same scheme core as the CLI:

- `SchemeRecipe`
- `resolve_scheme_steps()`
- `create_scheme_summary()`
- `finish_scheme_summary()`
- `evaluate_scheme_quality()`
- scheme review exporters

The GUI service writes a temporary draft scheme under `data/gui_drafts/schemes`,
but relative recipe/batch paths are resolved against the scheme path shown in
the GUI. This lets unsaved schemes still use paths such as
`../recipes/drain_iv_1k_resistor.yaml`.

Step intervals are not slept during GUI dry-runs. The current purpose is
artifact and workflow validation, not time-accurate scheduling.

## Current Scope

Supported:

- Dry-run scheme execution from GUI.
- Drain I-V dry-run steps with fake SMU.
- Single-gate dry-run steps with coupled fake SMUs.
- Nested Drain I-V batch dry-runs.
- Scheme report and CSV/SVG review artifacts.

Not yet included:

- GUI scheme hardware execution.
- Stop button for scheme dry-runs.
- Live per-step plot aggregation in the Schemes workspace.
- Loading older saved scheme folders in the GUI.

## User Checklist

- Launch `ptm-gui`.
- Open `Schemes`.
- Build or edit a scheme.
- Click `Form -> Scheme YAML`.
- Click `Check Scheme`.
- Click `Dry Run Scheme`.
- Confirm `Result` shows the scheme summary path and scheme quality.
- Open `Report` and confirm a Markdown report appears.
- Click `Scheme Folder` and confirm the saved folder contains
  `scheme_summary.json`.
- Click `Scheme Report` and confirm the report opens externally.

