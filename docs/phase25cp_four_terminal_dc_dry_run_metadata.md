# Phase 25cp: Four-Terminal DC Dry-Run Metadata Runner

This phase adds a dry-run-only artifact path for the future Keithley 2450
four-terminal DC measurement mode.

## Command

```powershell
ptm four-terminal-dc configs\recipes\four_terminal_dc_schema_draft.yaml --dry-run --fake-resistance-ohm 1000000 --progress
```

The same command without `--dry-run` exits with an error. Active four-terminal
Keithley output remains unimplemented and blocked.

## Artifacts

The dry-run writes the same basic run artifacts used by other measurement
families:

- `points.csv`
- `metadata.json`
- `recipe_snapshot.yaml`
- `safety_snapshot.yaml`

The metadata includes:

- `measurement_type: four_terminal_dc`
- `dry_run: true`
- `active_hardware_run_allowed: false`
- `contact_map`
- `dc_sense_mode`
- remote-sense SCPI plan: `:SENS:CURR:RSEN ON` and `:SENS:CURR:RSEN?`
- configured Keithley measurement conditions, including NPLC, ranges,
  terminal, source delay, and current compliance
- fake-model resistance/noise settings

## Safety Status

No instrument object is created and no output is enabled in this dry-run path.
The purpose is to stabilize artifact shape and metadata vocabulary before a
real remote-sense runner is designed.

NPLC remains a required measurement condition. The dry-run records it in
`configured_smu.nplc` and fake readback metadata so later active runs can use
the same metadata slots for lab verification.

## Lab Checklist

- [ ] Run the dry-run command.
- [ ] Confirm the command prints `Active hardware run allowed: False`.
- [ ] Open the printed run directory.
- [ ] Confirm `points.csv`, `metadata.json`, `recipe_snapshot.yaml`, and
  `safety_snapshot.yaml` exist.
- [ ] In `metadata.json`, confirm `measurement_type` is `four_terminal_dc`.
- [ ] Confirm `dry_run: true`.
- [ ] Confirm `configured_smu.nplc`, `voltage_range_v`, `current_range_a`, and
  `current_compliance_a` match the recipe.
- [ ] Confirm `remote_sense.configured_in_dry_run` is `false`.
- [ ] Do not run four-terminal DC hardware output yet.
