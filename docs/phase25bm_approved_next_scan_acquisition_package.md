# Phase 25bm: Approved Next-Scan Acquisition Package

## What Changed

- Added `ptm dual-gate-lockin-hall-suite-approved-next-scan-package`.
- The command packages approved next-scan Hall-suite recipes with:
  - copied hardware recipes
  - acquisition runbook
  - package manifest
  - ZIP archive
  - next-scan proposal JSON
  - approved next-scan review markdown

## Command

```powershell
ptm dual-gate-lockin-hall-suite-approved-next-scan-package configs\recipes\<approved_next_suite>\<prefix>_vxx.yaml configs\recipes\<approved_next_suite>\<prefix>_vxy_plus_b.yaml configs\recipes\<approved_next_suite>\<prefix>_vxy_minus_b.yaml data\hall_packages --zero-field-recipe configs\recipes\<approved_next_suite>\<prefix>_vxy_zero_b.yaml --proposal-json data\hall_packages\<previous_package>\hall_analysis\hall_suite_next_scan_proposal.json --approval-review configs\recipes\<approved_next_suite>\<prefix>_approved_next_scan_review.md --package-name <approved_next_package> --chunk-size <N>
```

## Package Policy

- Reuses the existing Hall-suite acquisition package path.
- Requires the next-scan proposal JSON and approved recipe review markdown.
- Copies those approval artifacts into the package notes.
- Adds `approved_next_scan` provenance to `package_manifest.json`.
- Appends `Approved Next-Scan Provenance` to the runbook.
- Rebuilds the ZIP after annotation so the archive matches the package folder.

## Lab Checklist

- [ ] Generate approved next-scan recipes first.
- [ ] Run Hall-suite check on the approved recipes.
- [ ] Create the approved next-scan package.
- [ ] Confirm the runbook shows the changed gate grid.
- [ ] Confirm the runbook shows preserved Keithley NPLC/range/compliance and
      SR860 settings.
- [ ] Confirm the ZIP contains copied recipes, proposal JSON, and approval
      review markdown.
- [ ] Use the chunked acquisition commands in the package runbook.
- [ ] After hardware acquisition, run result intake against this package before
      Hall analysis.

## Verification

- `python -m pytest tests\test_hall_suite_template.py -q`
- `python -m pytransport.cli dual-gate-lockin-hall-suite-approved-next-scan-package --help`
