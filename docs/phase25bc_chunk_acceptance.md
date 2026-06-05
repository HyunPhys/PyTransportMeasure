# Phase 25bc: Chunk Acceptance

This phase adds a checkpoint-specific acceptance gate for dual-gate lock-in
chunked hardware scans.

## What Changed

- Added `ptm dual-gate-lockin-chunk-audit`.
- The command audits a saved checkpoint run after
  `--stop-after-new-points <N>`.
- It expects:
  - `completed: false`
  - `abort_class: checkpoint`
  - `checkpoint_reached: true`
  - a valid measured prefix of the planned gate grid
- It still checks:
  - gate leakage and compliance flags
  - gate1/gate2 SMU readback
  - output-off cleanup and zero-before-off cleanup
  - SR860 probe and setting readback

## Usage

```powershell
ptm dual-gate-lockin-chunk-audit data\raw\<chunk_run_folder>
```

If the run was made with older metadata that lacks SR860 setting readback, the
lab can inspect the rest of the artifact with:

```powershell
ptm dual-gate-lockin-chunk-audit data\raw\<chunk_run_folder> --allow-missing-lockin-settings
```

Do not use that relaxation as evidence for expanding a hardware scan.

## Why It Matters

Strict `dual-gate-lockin-audit` is for completed full runs. A checkpoint chunk
is intentionally incomplete, so it needs a different acceptance condition:
the measured prefix must be clean, outputs must be off, and the run must be
safe to resume.

## Verification

- `python -m pytest tests\test_cli_dual_gate_lockin.py -q`
- `python -m pytransport.cli dual-gate-lockin-chunk-audit --help`
- `python -m pytest -q`
- `git diff --check`
