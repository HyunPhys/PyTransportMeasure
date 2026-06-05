# Phase 25ay: Dual-Gate Lock-In Chunk Plan

This phase adds a hardware-free runbook for executing a dual-gate lock-in grid
as multiple checkpoint chunks.

## What Changed

- Added `ptm dual-gate-lockin-chunk-plan`.
- The command splits the planned gate grid into fixed-size chunks.
- It prints:
  - total point count
  - chunk count
  - index and gate-voltage range for each chunk
  - `dual-gate-lockin-resume-check` commands between chunks
  - guarded `dual-gate-lockin --stop-after-new-points` command templates
- It exits nonzero when any chunk exceeds `--max-hardware-points`.

## Usage

```powershell
ptm dual-gate-lockin-chunk-plan configs\recipes\<dual_gate_lockin_recipe>.yaml --chunk-size <N> --max-hardware-points <N>
```

Then run the printed sequence one chunk at a time. Each checkpoint run should
turn outputs off and leave a partial artifact that can be checked before the
next chunk.

## Why It Matters

Large Hall-bar graphene maps should not require one long uninterrupted run from
the start. Chunk planning turns the map into small, auditable hardware
invocations that can be reviewed between steps.

## Verification

- `python -m pytest tests\test_dual_gate_lockin.py tests\test_cli_dual_gate_lockin.py tests\test_hall_suite_template.py -q`
- `python -m pytransport.cli dual-gate-lockin-chunk-plan --help`
- `python -m pytest -q`
- `git diff --check`
