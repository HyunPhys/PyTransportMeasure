# Phase 25bh: Hall-Suite Execution Result Intake

This phase adds a post-run intake command for Hall-bar dual-gate lock-in
packages.

## What Changed

- Added `ptm dual-gate-lockin-hall-suite-intake`.
- The command reads a package folder or `package_manifest.json`.
- It checks the packaged Vxx/+B Vxy/-B Vxy/0B Vxy recipe suite.
- It runs strict dual-gate lock-in acceptance audit on every supplied run folder.
- It compares each run's saved recipe snapshot against the packaged recipe.
- It checks each run's saved gate-grid signature against the packaged recipe.
- It verifies expected Vxx/Hall probe roles and +B/-B/0B magnetic-field
  metadata.
- It writes `result_intake_report.md` and `result_intake.json`.

## Example

```powershell
ptm dual-gate-lockin-hall-suite-intake data\hall_packages\<sample_lab_package> data\raw\<vxx_run> data\raw\<plus_B_run> data\raw\<minus_B_run> --zero-field-run-dir data\raw\<zero_B_run>
```

Use `--allow-missing-lockin-settings` only for dry-run or old metadata where
SR860 setting readback was not available. Real hardware intake should use the
strict default.

## PASS Criteria

- Packaged recipe suite consistency is PASS.
- Every supplied run passes strict dual-gate lock-in acceptance.
- Run recipe snapshots match the packaged recipes.
- Saved gate-grid signatures match the packaged recipes.
- Vxx run is longitudinal.
- +B and -B Hall runs are Hall role with equal-magnitude opposite magnetic
  fields.
- 0B Hall run, when supplied, is Hall role with `B = 0`.

## Lab Checklist

- [ ] Run intake after all Vxx/+B/-B/0B run folders are available.
- [ ] Confirm the command prints `Hall suite result intake: PASS`.
- [ ] Open `result_intake_report.md`.
- [ ] Continue to Hall antisymmetry, zero-field correction, and mobility
  analysis only after PASS.

## Verification

- `python -m pytest tests\test_hall_suite_template.py -q`
- `python -m pytransport.cli dual-gate-lockin-hall-suite-intake --help`
