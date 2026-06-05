# Phase 25ax: Dual-Gate Lock-In Checkpoint Stop

This phase adds an intentional checkpoint stop for long dual-gate lock-in scans.

## What Changed

- Added `--stop-after-new-points <N>` to `ptm dual-gate-lockin`.
- The runner stops after `N` newly measured points, even when the full recipe
  grid is larger.
- The run is saved as incomplete with:
  - `abort_class: checkpoint`
  - `checkpoint_requested: true`
  - `checkpoint_reached: true`
  - `points_measured_this_run`
  - `next_point_index`
- Normal cleanup still runs:
  - gate voltages are commanded to 0 V
  - Keithley outputs are turned off
  - partial CSV and metadata are written
- The hardware point guard now checks the bounded invocation size when
  `--stop-after-new-points` is supplied.

## Usage

Run only the first few new points:

```powershell
ptm dual-gate-lockin configs\recipes\<dual_gate_lockin_recipe>.yaml --allow-active-sweep --stop-after-new-points <N> --max-hardware-points <N> --yes --progress
```

Continue later:

```powershell
ptm dual-gate-lockin-resume-check configs\recipes\<dual_gate_lockin_recipe>.yaml data\raw\<checkpoint_run_folder>
ptm dual-gate-lockin configs\recipes\<dual_gate_lockin_recipe>.yaml --allow-active-sweep --resume-from-run data\raw\<checkpoint_run_folder> --stop-after-new-points <N> --max-hardware-points <N> --yes --progress
```

## Why It Matters

Large Hall-bar dual-gate maps should be expandable in deliberate chunks. This
lets the lab verify leakage, lock-in signal level, drift, and output cleanup
before committing to a full gate grid.

## Verification

- `python -m pytest tests\test_dual_gate_lockin.py tests\test_cli_dual_gate_lockin.py -q`
- `python -m pytransport.cli dual-gate-lockin --help`
- `python -m pytest -q`
- `git diff --check`
