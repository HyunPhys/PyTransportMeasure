# Phase 25i: Dual-Gate Lock-In Limited Active Sweep

This phase enables the first guarded active dual-gate lock-in sweep.

## Command

```powershell
ptm dual-gate-lockin configs/recipes/dual_gate_lockin_limited_active.yaml --allow-active-sweep --max-hardware-points 4 --progress --plot --report --gate-stats
```

## Guard Rails

Hardware sweep execution is blocked unless:

- `--allow-active-sweep` is supplied
- the recipe point count is no larger than `--max-hardware-points`
- the three-instrument preflight passes
- the operator confirms the prompt unless `--yes` is supplied

The default `configs/recipes/dual_gate_lockin_dry_run.yaml` has 25 points and is
blocked by the default hardware point guard.

## Safety Behavior

The existing dual-gate lock-in runner is used for the active sweep. It configures
both gate Keithleys with recipe compliance/range/terminal/NPLC settings, enables
gate outputs, records leakage and SR860 X/Y/R/theta, and turns both outputs off
on completion, safety stop, exception, or interrupt.

Metadata records:

- `gate_outputs_enabled: false` after cleanup
- `outputs_off_after_run: true`
- any `triggered_limit`

## Next Step

Before broad scans, define interruption and resume policy for active dual-gate
lock-in sweeps.
