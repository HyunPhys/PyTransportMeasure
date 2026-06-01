# Phase 18 - Method Registry Planning Dispatch

This phase extends the method registry from saved-run review behavior into
recipe loading and plan formatting.

## What Changed

- `pytransport/method_registry.py` now records:
  - recipe loader
  - plan formatter
  - saved-run summary formatter
  - plot writer
  - report writer
  - campaign summary field mapper
- `ptm plan` now uses the Drain I-V method handler internally.
- `ptm single-gate-plan` now uses the single-gate method handler internally.
- `ptm run` and `ptm single-gate` print their pre-run plans through the same
  method handlers.
- `scheme-plan` formats Drain I-V and single-gate steps through the registry.

## Why This Matters

New measurement methods need two kinds of support before hardware execution:

- load and validate their recipe
- preview the exact intended measurement plan

Putting those hooks in the method registry makes future 4-probe, lock-in, AC,
and pulse methods easier to add without teaching every CLI path how each method
formats its own plan.

## Current Boundary

Hardware runner dispatch remains explicit and command-specific:

- `ptm run` executes Drain I-V.
- `ptm single-gate` executes single-gate sweeps.
- scheme execution still calls method-specific runner helpers.

This is intentional. The hardware-running path should move more carefully than
the planning and saved-run review paths.

## Verification

Validated commands:

```powershell
python -m pytest
python -m pytransport.cli plan configs/recipes/drain_iv_1k_resistor.yaml
python -m pytransport.cli single-gate-plan configs/recipes/single_gate_dry_run.yaml
python -m pytransport.cli scheme-plan configs/schemes/single_gate_dry_run_scheme.yaml
```

