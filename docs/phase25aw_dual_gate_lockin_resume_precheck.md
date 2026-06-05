# Phase 25aw: Dual-Gate Lock-In Resume Precheck

This phase adds a hardware-free check before resuming an interrupted dual-gate
lock-in sweep.

## What Changed

- Added `ptm dual-gate-lockin-resume-check <recipe> <partial_run_dir>`.
- The check reuses the same resume compatibility rules as the runner:
  - source run must be an incomplete `dual_gate_lockin_sweep`
  - `metadata.json` and `points.csv` must exist
  - planned gate-grid signature must match the current recipe
  - `points.csv` must contain a contiguous prefix starting at index 0
- The report prints:
  - PASS/FAIL
  - planned, copied, and remaining point counts
  - next point index
  - next gate indices and gate voltages

## Usage

```powershell
ptm dual-gate-lockin-resume-check configs\recipes\<dual_gate_lockin_recipe>.yaml data\raw\<partial_run_folder>
```

Run this before:

```powershell
ptm dual-gate-lockin configs\recipes\<dual_gate_lockin_recipe>.yaml --allow-active-sweep --resume-from-run data\raw\<partial_run_folder> --max-hardware-points <N> --hardware-approval-note "<lab note>" --accepted-previous-run data\raw\<accepted_run> --yes --progress --plot --report --gate-stats
```

## Why It Matters

Resume support is useful only if it is hard to misuse. This precheck lets the
lab laptop confirm that the partial run and the recipe describe the same gate
grid before any Keithley output can be enabled.

## Verification

- `python -m pytest tests\test_dual_gate_lockin.py tests\test_cli_dual_gate_lockin.py tests\test_hall_suite_template.py -q`
- `python -m pytransport.cli dual-gate-lockin-resume-check --help`
- `python -m pytest -q`
- `git diff --check`
