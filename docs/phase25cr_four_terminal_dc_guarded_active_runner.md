# Phase 25cr: Four-Terminal DC Guarded Active Runner Draft

This phase adds a guarded active-run draft for Keithley 2450 four-terminal DC
remote-sense measurements.

## Command

The active path is blocked unless all guard flags are supplied:

```powershell
ptm four-terminal-dc configs\recipes\four_terminal_dc_schema_draft.yaml --allow-active-run --command-review-json docs\four_terminal_dc_command_review.json --hardware-approval-note "fixture contacts checked; preflight passed" --max-hardware-points 3 --yes --progress
```

Dry-run remains available and should be used first:

```powershell
ptm four-terminal-dc configs\recipes\four_terminal_dc_schema_draft.yaml --dry-run --fake-resistance-ohm 1000000 --progress
```

## Required Guards

- `--allow-active-run`
- passing `--command-review-json` with `evidence_passed: true`
- non-empty `--hardware-approval-note`
- `--max-hardware-points` greater than or equal to the recipe point count
- passing hardware preflight immediately before the runner opens the SMU
- interactive confirmation unless `--yes` is supplied

The command-review JSON itself remains non-authorizing. It proves evidence and
sequence shape; the active CLI flags and live preflight provide the final gate.

## Runner Behavior

The active draft:

- validates recipe safety
- configures voltage-source/current-measure settings with explicit NPLC,
  voltage range, current range, source delay, and compliance
- compares SMU readback before output
- enables current remote sense with `:SENS:CURR:RSEN ON`
- requires `:SENS:CURR:RSEN?` to confirm ON before output
- writes `points.csv`, `metadata.json`, `recipe_snapshot.yaml`, and
  `safety_snapshot.yaml`
- records `hardware_guard`, `configured_smu`, `configured_smu_readback`,
  `remote_sense`, and `output_state` metadata
- attempts zero-before-off, output off, and `:SENS:CURR:RSEN OFF` cleanup in
  normal, error, and interrupt paths

## Lab Checklist

- [ ] Confirm force/sense contacts are connected to the intended terminals.
- [ ] Run four-terminal DC preflight and save JSON.
- [ ] Run four-terminal DC dry-run and keep metadata.
- [ ] Run command review with both evidence files and confirm every evidence
  check is PASS.
- [ ] Confirm recipe point count is no larger than `--max-hardware-points`.
- [ ] Use a tiny sweep and conservative compliance for the first active smoke.
- [ ] Confirm Keithley output turns off after the run.
- [ ] Confirm `metadata.json` has `remote_sense.enabled_readback_ok: true`.
- [ ] Confirm `remote_sense.disabled_after_run_readback` is `0` or `OFF`.
- [ ] Confirm `output_state.instrument.off_after_run: true`.
