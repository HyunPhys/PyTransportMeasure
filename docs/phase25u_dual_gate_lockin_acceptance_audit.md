# Phase 25u: Dual-Gate Lock-In Acceptance Audit

## Goal

Add a saved-run audit that decides whether a limited dual-gate lock-in active
sweep is clean enough to use as evidence before expanding the hardware scan.

This does not enlarge the scan by itself. It creates the checkpoint that should
pass before a larger Hall-bar graphene gate grid is attempted.

## Command

```powershell
ptm dual-gate-lockin-audit data\raw\<dual_gate_lockin_run_folder> --write-report
```

The command prints `PASS` or `FAIL`. With `--write-report`, it writes:

- `dual_gate_lockin_acceptance.md`

## Acceptance Checks

The audit checks:

- saved metadata is a `dual_gate_lockin_sweep`
- run completed with `abort_class: completed`
- `points_written == planned_points`
- `remaining_points == 0`
- `points.csv` row count matches metadata
- gate1 and gate2 SMU readback checks are available and matched
- gate1 and gate2 NPLC were explicitly declared, or a warning is emitted
- both gate outputs are marked off after run
- both gate channels successfully commanded 0 V before output off
- final commanded voltage for both gate roles is 0 V
- lock-in probe metadata exists
- SR860 error/status fields are zero when present
- declared SR860 settings match the saved SR860 setting readback

Dry-run fake lock-ins do not provide real SR860 setting readback. For dry-run
artifact checks only, use:

```powershell
ptm dual-gate-lockin-audit data\raw\<dry_run_folder> --allow-missing-lockin-settings
```

Do not use that relaxation as evidence for expanding a real hardware scan.

## Measurement Rationale

For the Hall-bar graphene path, a larger dual-gate scan should only happen
after the previous limited run proves:

- the intended Keithley settings, including NPLC, were accepted by the
  instruments
- the SR860 state matched the recipe
- every planned gate point was written
- no safety stop or exception occurred
- the runner returned both gate outputs to a zero/off state

This keeps broad scan decisions tied to run artifacts rather than memory or
front-panel assumptions.
