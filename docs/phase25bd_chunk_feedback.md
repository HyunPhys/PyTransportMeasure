# Phase 25bd: Chunk Feedback

This phase adds a feedback summary command for early dual-gate lock-in chunked
hardware scans.

## What Changed

- Added `ptm dual-gate-lockin-chunk-feedback`.
- The command accepts one or more checkpoint chunk run folders.
- It runs checkpoint acceptance on each chunk and summarizes:
  - pass/fail per chunk
  - maximum gate1/gate2 leakage
  - minimum gate1/gate2 leakage/compliance margin
  - continue/review recommendations
- The broader scan packet now prints a chunk feedback command after the chunk
  acquisition/audit sequence.

## Usage

```powershell
ptm dual-gate-lockin-chunk-feedback data\raw\<chunk_01_run> data\raw\<chunk_02_run> --output docs\<sample>_chunk_feedback.md
```

## Why It Matters

The first chunks are where the lab decides whether the planned measurement
parameters are sensible. This command keeps that decision tied to saved
artifacts instead of memory: leakage margins, SR860 setting readback, and
checkpoint cleanliness all have to agree before continuing with the same chunk
size, NPLC, settle time, and lock-in sensitivity.

## Verification

- `python -m pytest tests\test_cli_dual_gate_lockin.py -q`
- `python -m pytransport.cli dual-gate-lockin-chunk-feedback --help`
- `python -m pytest -q`
- `git diff --check`
