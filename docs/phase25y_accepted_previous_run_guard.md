# Phase 25y: Accepted Previous Run Guard

This phase strengthens the dual-gate lock-in hardware scale-up rule. A raised
hardware point guard now needs both an operator note and a saved accepted run.

## Scope

- Add `--accepted-previous-run` to `ptm dual-gate-lockin`.
- Require it whenever `--max-hardware-points` is raised above the default guard.
- Run strict `ptm dual-gate-lockin-audit` logic on the previous run before any
  new hardware output can be enabled.
- Save previous-run evidence in `metadata.json` under `hardware_guard`.

## Policy

The default active dual-gate lock-in guard remains 9 hardware points. To run a
larger grid, first complete a limited active run and audit it:

```powershell
ptm dual-gate-lockin-audit data\raw\<limited_run_folder> --write-report
```

Only if that audit prints `Dual-gate lock-in acceptance: PASS`, run the broader
scan with the accepted run folder:

```powershell
ptm dual-gate-lockin configs/recipes/dual_gate_lockin_limited_active.yaml --allow-active-sweep --max-hardware-points 25 --hardware-approval-note "2x2 accepted; expanding to 5x5" --accepted-previous-run data\raw\<limited_run_folder> --progress --plot --report --gate-stats
```

## Metadata

Raised-guard hardware runs now record:

- `hardware_guard.accepted_previous_run`
- `hardware_guard.accepted_previous_run_audit_passed`
- `hardware_guard.accepted_previous_run_points_written`
- `hardware_guard.accepted_previous_run_planned_points`

This keeps broader Hall-bar scans traceable to a concrete, accepted lab
artifact rather than only a free-text note.

## Lab Checklist

- Confirm the limited active run completes and writes `points.csv`.
- Run strict `ptm dual-gate-lockin-audit ... --write-report`.
- Confirm the audit result is `PASS`.
- Use the passing run folder as `--accepted-previous-run` for any raised point
  guard.
- Confirm the new run metadata records the accepted previous run path and audit
  pass state.
