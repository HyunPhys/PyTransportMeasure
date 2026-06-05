# Phase 25av: Dual-Gate Lock-In Resume

This phase adds restart support for interrupted dual-gate lock-in sweeps.

## What Changed

- Added `--resume-from-run <run_dir>` to `ptm dual-gate-lockin`.
- Resume creates a new run directory. It does not modify the original partial
  run.
- The runner copies the previous `points.csv` rows first, then measures the
  remaining gate-grid points.
- Resume is allowed only when:
  - the source run is an incomplete `dual_gate_lockin_sweep`
  - the source `metadata.json` and `points.csv` exist
  - the saved planned gate-grid signature matches the current recipe
  - the source `points.csv` contains a contiguous prefix starting at index 0
- Metadata records:
  - `resume_from_run`
  - `resume_source_metadata_path`
  - `resume_source_csv_path`
  - `resume_next_point_index`
  - `points_copied_from_resume`
  - `points_measured_this_run`

## Usage

Dry-run:

```powershell
ptm dual-gate-lockin configs\recipes\<dual_gate_lockin_recipe>.yaml --dry-run --resume-from-run data\raw\<partial_run_folder>
```

Guarded hardware:

```powershell
ptm dual-gate-lockin configs\recipes\<dual_gate_lockin_recipe>.yaml --allow-active-sweep --resume-from-run data\raw\<partial_run_folder> --max-hardware-points <N> --hardware-approval-note "<lab note>" --accepted-previous-run data\raw\<accepted_run> --yes --progress --plot --report --gate-stats
```

## Why It Matters

Hall-bar graphene dual-gate scans can be long. A run may stop because of a user
interrupt, transient communication error, or a conservative safety review point.
Resume support makes larger scans more practical while preserving raw partial
artifacts for review.

## Verification

- `python -m pytest tests\test_dual_gate_lockin.py tests\test_cli_dual_gate_lockin.py -q`
- `python -m pytransport.cli dual-gate-lockin --help`
- `python -m pytest -q`
- `git diff --check`
