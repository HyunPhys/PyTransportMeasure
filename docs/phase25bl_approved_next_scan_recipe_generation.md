# Phase 25bl: Approved Next-Scan Recipe Generation

## What Changed

- Added `ptm dual-gate-lockin-hall-suite-approved-next-scan`.
- The command turns an advisory next-scan proposal into a new Hall-suite recipe
  set only when a lab approval note is supplied.
- It writes Vxx, +B Vxy, -B Vxy, and optional 0B Vxy recipes plus an approval
  review markdown file.

## Command

```powershell
ptm dual-gate-lockin-hall-suite-approved-next-scan data\hall_packages\<sample_lab_package>\hall_analysis configs\recipes\<approved_next_suite> --approval-note "<lab notebook approval>" --measurement-prefix <approved_prefix>
```

The command accepts either `hall_suite_next_scan_proposal.json` or its parent
`hall_analysis` directory.

## Safety Policy

- `--approval-note` is required before writing hardware recipes.
- The proposal must declare `requires_lab_approval: true`.
- The proposal must still be advisory with `hardware_recipe_written: false`.
- The generator only applies approved gate `start_v`, `stop_v`, and `points`.
- Keithley NPLC, voltage range, current range, current compliance, source
  delay, gate settle time, and SR860 settings are copied from the packaged
  recipes by default.

## Lab Checklist

- [ ] Run suite review and next-scan proposal first.
- [ ] Record approval in the lab notebook.
- [ ] Run the approved next-scan generator with the approval note.
- [ ] Open the generated approval review markdown.
- [ ] Confirm gate start/stop/points are the intended next scan.
- [ ] Confirm NPLC/range/compliance/SR860 settings were preserved unless the
      lab explicitly approved changing them.
- [ ] Run `ptm dual-gate-lockin-hall-suite-check` on the generated recipes.
- [ ] Create a new acquisition package before hardware use.

## Verification

- `python -m pytest tests\test_hall_suite_template.py -q`
- `python -m pytransport.cli dual-gate-lockin-hall-suite-approved-next-scan --help`
