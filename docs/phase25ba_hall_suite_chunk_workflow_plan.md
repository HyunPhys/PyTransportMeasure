# Phase 25ba: Hall Suite Chunk Workflow Plan

This phase adds one hardware-free runbook for chunked Hall-bar suite
acquisition.

## What Changed

- Added `ptm dual-gate-lockin-hall-suite-chunk-plan`.
- The command accepts Vxx, `+B` Vxy, `-B` Vxy, and optional `0B` Vxy recipes.
- It runs the Hall-suite consistency check first.
- If compatible, it prints:
  - per-recipe `dual-gate-lockin-chunk-plan` commands
  - chunk acquisition notes for each Vxx/Vxy role
  - per-recipe `dual-gate-lockin-stitch-chunks` commands
  - Hall antisymmetry, zero-field correction, and mobility commands using
    stitched run folders

## Usage

```powershell
ptm dual-gate-lockin-hall-suite-chunk-plan configs\recipes\<suite>\<prefix>_vxx.yaml configs\recipes\<suite>\<prefix>_vxy_plus_b.yaml configs\recipes\<suite>\<prefix>_vxy_minus_b.yaml --zero-field-recipe configs\recipes\<suite>\<prefix>_vxy_zero_b.yaml --chunk-size <N>
```

## Why It Matters

Hall-bar graphene mapping is a suite-level measurement: Vxx, `+B` Vxy, `-B`
Vxy, optional `0B` Vxy, stitching, then Hall/mobility analysis. This command
keeps the full workflow visible before any hardware output is enabled.

## Verification

- `python -m pytest tests\test_hall_suite_template.py -q`
- `python -m pytransport.cli dual-gate-lockin-hall-suite-chunk-plan --help`
- `python -m pytest -q`
- `git diff --check`
