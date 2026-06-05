# Phase 25bv: Hall Package Manifest Schema Cleanup

## Summary

Hall-suite acquisition package manifests now include a normalized
`measurement_condition_audits` block while preserving the existing
`keithley_parameter_audits` and `lockin_setting_audits` fields.

## Manifest Version

New packages write:

```json
{
  "manifest_schema_version": 2,
  "measurement_condition_audits": {
    "schema_version": 1,
    "ok_for_hardware": true,
    "records": []
  }
}
```

Each record has a stable shape:

- `recipe_key`
- `instrument`
- `audit_type`
- `json`
- `markdown`
- `ok_for_hardware`
- `summary`

## Backward Compatibility

The workflow status reader still accepts older manifests that only contain:

- `keithley_parameter_audits`
- `lockin_setting_audits`

When `measurement_condition_audits.records` exists, it is used as the primary
source for Keithley and SR860 audit status.

## Why

The package manifest is becoming the handoff contract between development
machine, lab laptop, GUI, analysis scripts, and lab notebook artifacts. A
normalized audit record makes external scripts easier to write and reduces
special-case parsing as more instrument types are added.

## Lab Checklist

- [ ] Confirm new packages have `manifest_schema_version: 2`.
- [ ] Confirm `measurement_condition_audits.ok_for_hardware: true`.
- [ ] Confirm each record points to existing JSON and Markdown audit files.
- [ ] Existing packages with legacy audit fields remain readable by
      `ptm dual-gate-lockin-hall-suite-status`.
