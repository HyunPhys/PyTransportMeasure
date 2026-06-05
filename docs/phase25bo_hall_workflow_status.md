# Phase 25bo: Hall Workflow Command Consolidation

## What Changed

- Added `ptm dual-gate-lockin-hall-suite-status`.
- The command gives one read-only status summary for a Hall-suite package.
- It can optionally write the status as JSON with `--json-output`.

## Command

```powershell
ptm dual-gate-lockin-hall-suite-status data\hall_packages\<approved_next_package>
```

Optional JSON:

```powershell
ptm dual-gate-lockin-hall-suite-status data\hall_packages\<approved_next_package> --json-output docs\<package>_status.json
```

## Stages Checked

- package manifest
- acquisition runbook
- package ZIP
- copied recipes
- approved next-scan provenance
- result intake
- Hall analysis
- analysis review
- next-scan proposal
- dry-run rehearsal

## Policy

This command is read-only. It does not run hardware, does not create
measurement artifacts, and does not alter package recipes. Use it before lab
handoff to see which workflow stages exist and which ones need review.

## Lab Checklist

- [ ] Run the status command on the package folder.
- [ ] Confirm package manifest, runbook, ZIP, and copied recipes are PASS.
- [ ] Confirm approved next-scan provenance is PASS for approved packages.
- [ ] Confirm dry-run rehearsal is PASS before lab handoff when available.
- [ ] Treat missing intake/analysis/review/proposal as expected before hardware
      acquisition, and as missing work after completed acquisition.

## Verification

- `python -m pytest tests\test_hall_suite_template.py -q`
- `python -m pytransport.cli dual-gate-lockin-hall-suite-status --help`
