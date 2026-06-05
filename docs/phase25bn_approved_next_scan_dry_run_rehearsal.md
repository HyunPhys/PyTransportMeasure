# Phase 25bn: Approved Next-Scan Dry-Run Package Rehearsal

## What Changed

- Added `ptm dual-gate-lockin-hall-suite-approved-next-scan-rehearse`.
- The command runs an approved next-scan acquisition package through a complete
  hardware-free loop:
  - fake Vxx/+B/-B/0B acquisition
  - result intake
  - Hall analysis
  - analysis review
  - next-scan proposal

## Command

```powershell
ptm dual-gate-lockin-hall-suite-approved-next-scan-rehearse data\hall_packages\<approved_next_package>
```

By default, outputs are written to:

```text
data\hall_packages\<approved_next_package>\dry_run_rehearsal
```

Use `--overwrite` to regenerate the rehearsal folder.

## Rehearsal Policy

- Requires the package manifest to contain `approved_next_scan` provenance.
- Copies the packaged recipes into a rehearsal manifest.
- Changes only the copied rehearsal recipes' output directory, so strict intake
  can compare fake run metadata against the rehearsal package recipes.
- Leaves the original package recipes and package manifest untouched.
- Uses fake dual-gate Keithley/SR860 instruments only.

## Lab Checklist

- [ ] Create an approved next-scan package.
- [ ] Run the rehearsal command before lab handoff.
- [ ] Confirm `rehearsal_summary.json` has `completed: true`.
- [ ] Confirm fake runs were written under `dry_run_rehearsal/runs`.
- [ ] Confirm result intake, Hall analysis, analysis review, and next proposal
      were produced.
- [ ] Confirm `approved_next_scan` provenance is present in the rehearsal
      summary.

## Verification

- `python -m pytest tests\test_hall_suite_template.py -q`
- `python -m pytransport.cli dual-gate-lockin-hall-suite-approved-next-scan-rehearse --help`
