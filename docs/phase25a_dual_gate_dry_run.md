# Phase 25a - Dual-Gate Dry-Run Foundation

This phase adds the first explicit dual-gate measurement method for the Hall bar
graphene target workflow.

## What Changed

- Added `DualGateRecipe` with separate `drain_instrument`,
  `gate1_instrument`, and `gate2_instrument` blocks.
- Added independent `gate1_sweep`, `gate2_sweep`, and `drain_sweep` blocks.
- Added a dry-run runner over `gate1 x gate2 x drain` points.
- Added fake dual-gate SMU state with independent gate leakage and modulation
  parameters.
- Added dual-gate review artifacts:
  - `points.csv`
  - `metadata.json`
  - `dual_gate_heatmap.svg`
  - `dual_gate_stats.csv`
  - `dual_gate_report.md`
- Registered `dual_gate_sweep` with the common method registry so saved-run
  `summarize`, `plot`, and `report` commands dispatch correctly.

## Current Hardware Policy

`ptm dual-gate` requires `--dry-run`. Non-dry-run hardware execution is blocked
until the real topology is chosen and smoke-tested.

This is intentional because a DC dual-gate Drain I-V method needs independent
drain, gate1, and gate2 source roles. The current lab hardware description has
two Keithley 2450s and one SR860, so the likely next real hardware path may be
an AC method where the two Keithleys bias the gates and SR860 measures the
source-drain response.

## Commands

```powershell
ptm dual-gate-plan configs/recipes/dual_gate_dry_run.yaml
ptm dual-gate configs/recipes/dual_gate_dry_run.yaml --dry-run --summary --plot --report --gate-stats --fake-noise-std-a 0
```

## Next Step

Define the real Hall bar dual-gate hardware topology:

- DC path: add a third source role or a verified alternative drain bias source.
- AC path: use two Keithleys for gate biases and SR860 for source-drain
  response.
- In either case, add preflight before enabling hardware output.
