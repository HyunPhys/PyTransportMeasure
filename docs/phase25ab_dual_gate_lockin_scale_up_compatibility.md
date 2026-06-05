# Phase 25ab: Dual-Gate Lock-In Scale-Up Compatibility

This phase connects the accepted previous run artifact to the candidate broader
scan recipe. A previous run is no longer enough just because it passed
acceptance; it also has to be compatible with the recipe about to run.

## Scope

When `ptm dual-gate-lockin` raises `--max-hardware-points` above the default
guard, the CLI now:

- audits `--accepted-previous-run` strictly,
- compares the accepted run metadata with the candidate recipe,
- blocks before preflight/output if the candidate recipe is not compatible,
- saves the compatibility result in `metadata.json` under `hardware_guard`.

## Compatibility Checks

The scale-up audit checks:

- measurement geometry matches,
- Hall-bar topology block matches,
- SR860 lock-in recipe settings match,
- gate1/gate2 Keithley settings match,
- gate compliance is unchanged,
- gate settle time is not shortened,
- candidate gate grid contains every point from the accepted previous grid.

This keeps the accepted previous run tied to the actual measurement condition,
not only to a free-text note.

## Metadata

Raised-guard hardware runs now record:

- `hardware_guard.accepted_previous_run_scale_up_compatible`
- `hardware_guard.accepted_previous_run_grid_signature`

## Lab Checklist

- Run and audit a limited active sweep.
- Use the accepted folder as `--accepted-previous-run`.
- Confirm the raised run prints
  `Dual-gate lock-in scale-up compatibility: PASS`.
- If compatibility fails, review whether topology, lock-in settings, SMU
  settings, compliance, settle time, or the broader gate grid changed.
