# Phase 25be: Recipe Adjustment

This phase adds a hardware-free adjustment command for dual-gate lock-in
recipes after lab feedback.

## What Changed

- Added `ptm dual-gate-lockin-adjust-recipe`.
- The command copies a validated base recipe and changes only selected
  measurement parameters:
  - gate1/gate2 or shared gate NPLC
  - gate1/gate2 or shared gate settle time
  - SR860 sensitivity index
  - SR860 time constant index
  - SR860 settle time constants
  - explicit SR860 read-settle override
- It can also set a new measurement name, output directory, and adjustment note.
- It writes an adjustment review markdown unless `--no-review` is supplied.

## Usage

```powershell
ptm dual-gate-lockin-adjust-recipe configs\recipes\<candidate_recipe>.yaml configs\recipes\<adjusted_recipe>.yaml --gate-nplc <NPLC> --gate-settle-s <seconds> --lockin-sensitivity-index <index> --lockin-time-constant-index <index> --lockin-settle-time-constants <N> --adjustment-note "<lab feedback>"
```

## Why It Matters

After the first chunks, the lab may need to slow down gate leakage readback,
increase settling, or change SR860 range/time-constant settings. This command
keeps those changes explicit, validated, and reviewable while preserving the
gate grid and topology.

## Verification

- `python -m pytest tests\test_cli_dual_gate_lockin.py -q`
- `python -m pytransport.cli dual-gate-lockin-adjust-recipe --help`
- `python -m pytest -q`
- `git diff --check`
