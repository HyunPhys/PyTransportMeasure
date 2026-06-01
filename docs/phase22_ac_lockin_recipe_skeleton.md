# Phase 22 - AC / Lock-In Recipe Skeleton

This phase adds a dry-run-only AC / lock-in bias-sweep skeleton. It validates
recipe shape, point columns, metadata, summary, plot, report, and method-registry
dispatch without controlling real SR860 hardware yet.

## What Changed

- Added `AcLockInRecipe`.
- Added `ac_lockin_sweep` as a registered measurement type.
- Added `ptm ac-lockin-plan`.
- Added `ptm ac-lockin --dry-run`.
- Added `configs/recipes/ac_lockin_dry_run.yaml`.
- Added lock-in-aware point columns:
  - `bias_voltage_v`
  - `source_current_a`
  - `lockin_x_v`
  - `lockin_y_v`
  - `lockin_r_v`
  - `lockin_theta_deg`
- Added AC lock-in summary, SVG plot, and Markdown report helpers.
- Added campaign/index awareness for the new measurement type.

## Current Boundary

Hardware AC lock-in runs are intentionally blocked. The command returns an error
unless `--dry-run` is passed.

This means no active code path talks to a real SR860 yet. The current milestone
only proves the recipe and artifact flow.

## Commands

```powershell
ptm ac-lockin-plan configs/recipes/ac_lockin_dry_run.yaml
ptm ac-lockin configs/recipes/ac_lockin_dry_run.yaml --dry-run --summary --plot --report --fake-resistance-ohm 1000000 --fake-lockin-r-v 0.000002 --fake-lockin-phase-deg 30 --fake-noise-std 0
```

Expected dry-run result:

- `completed=True`
- `points=11`
- `ac_lockin_plot.svg`
- `ac_lockin_report.md`
- lock-in columns in `points.csv`

## Next

- Add SR860 hardware driver after command confirmation.
- Add hardware smoke-test recipe with conservative lock-in/source settings.
- Add lock-in-aware campaign/report refinements if needed after real data exists.

