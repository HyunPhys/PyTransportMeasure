# Phase 25az: Dual-Gate Lock-In Chunk Stitching

This phase adds a hardware-free stitch step for checkpointed dual-gate lock-in
maps.

## What Changed

- Added `ptm dual-gate-lockin-stitch-chunks`.
- The command accepts one or more chunk run folders.
- For each chunk, it keeps only newly measured rows after
  `points_copied_from_resume`.
- It validates:
  - every source is a `dual_gate_lockin_sweep`
  - planned gate-grid signatures match
  - planned point counts match
  - stitched row indices are contiguous from 0
- It writes a new standard dual-gate lock-in run folder with:
  - `points.csv`
  - `metadata.json`
  - copied recipe/safety snapshots when available
  - optional stats, plot, report, and run-index artifacts

## Usage

```powershell
ptm dual-gate-lockin-stitch-chunks data\raw\<chunk_01_run> data\raw\<chunk_02_run> data\raw\<chunk_03_run> --measurement-name <stitched_name> --gate-stats --plot --report
```

## Why It Matters

Chunked hardware acquisition is safer for long Hall-bar maps, but analysis
should still see one coherent gate grid. Stitching converts checkpoint chunks
back into a standard run artifact so the existing summary, heatmap, report, Hall
antisymmetry, and mobility analysis paths can operate normally.

## Verification

- `python -m pytest tests\test_dual_gate_lockin.py tests\test_cli_dual_gate_lockin.py -q`
- `python -m pytransport.cli dual-gate-lockin-stitch-chunks --help`
- `python -m pytest -q`
- `git diff --check`
