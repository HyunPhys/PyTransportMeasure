# Phase 25bx: Hall Package Manifest Validator

## Summary

Added a dedicated hardware-free package validator:

```powershell
ptm dual-gate-lockin-hall-suite-validate-package data\hall_packages\<package> --json-output data\hall_packages\<package>\package_validation.json
```

This command validates the Hall-suite acquisition package itself, separate from
workflow progress status.

## What It Checks

- `package_manifest.json` exists and declares `manifest_schema_version: 2`.
- `package_name` is present.
- `acquisition_runbook.md` exists.
- The package ZIP exists next to the package directory.
- Required copied recipes exist for `longitudinal`, `plus`, and `minus`; `zero`
  is checked when present.
- `measurement_condition_audits.schema_version` is `1`.
- Normalized audit records exist for both `keithley_2450` and `srs_sr860`.
- Every normalized audit record is hardware-ready and its JSON/Markdown
  artifact path exists.

## Output

The command prints a table for human lab review and can write machine-readable
JSON for GUI/package-inspection tools. The JSON contains:

- `valid`
- `checks`
- `issues`
- `manifest_schema_version`
- `recipe_count`

## Lab Checklist

- [ ] Run the validator before moving a package to the lab laptop.
- [ ] Confirm the command exits `0`.
- [ ] Confirm the text output says `Valid for lab handoff: True`.
- [ ] Save `package_validation.json` next to the package if the package will be
  archived or shared.
