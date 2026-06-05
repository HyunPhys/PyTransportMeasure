# Phase 25l: Dual-Gate Lock-In Scan Readiness Gate

This phase makes dual-gate lock-in plans and preflights clearer before any
broader hardware scan is attempted.

## Scope

- Add a `Scan readiness` block to `ptm dual-gate-lockin-plan`.
- Add the same readiness block to `ptm dual-gate-lockin-preflight`.
- Report:
  - gate1 x gate2 point count,
  - gate voltage steps,
  - minimum programmed settle time,
  - default hardware point guard status,
  - nominal source-drain AC current.
- Keep broad hardware scans blocked by the existing point guard unless the
  operator explicitly raises `--max-hardware-points`.

## Policy

This phase does not decide a safe broad-scan size. That decision should come
from lab feedback after the limited 2x2 active sweep, SR860 setting readback,
leakage behavior, and recovery metadata have all been checked.

## Lab Checklist

```powershell
ptm dual-gate-lockin-plan configs/recipes/dual_gate_lockin_dry_run.yaml
ptm dual-gate-lockin-preflight configs/recipes/dual_gate_lockin_limited_active.yaml
```

- Confirm `Scan readiness` appears in both outputs.
- Confirm the broader dry-run recipe reports `Within default point guard:
  False`.
- Confirm the limited active recipe reports `Within default point guard: True`.
- Do not raise `--max-hardware-points` until the limited active sweep artifacts
  look correct.
