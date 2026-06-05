# Phase 25dad: Hall Lab Smoke Measurement Parameter Audit

## Summary

This phase adds per-recipe measurement-condition audit commands to the Hall lab
smoke bundle. The package manifest already contains normalized Keithley/SR860
audit records, but the lab smoke checklist now makes the same check explicit in
the operator workflow before hardware preflight.

## New Lab Smoke Commands

Each `lab_smoke/lab_smoke_checklist.md` now includes commands like:

```powershell
ptm measurement-parameter-audit dual_gate_lockin_sweep data\hall_packages\<package>\recipes\<recipe>.yaml --json-output data\hall_packages\<package>\lab_smoke\<recipe_key>_measurement_parameter_audit.json
```

These commands are generated for every packaged recipe role:

- `longitudinal`
- `plus`
- `minus`
- `zero`, when present

## Why

Hall-bar scans depend on stable Keithley and SR860 measurement conditions.
Putting the combined audit directly in the lab smoke checklist makes the
operator confirm NPLC, ranges, compliance, SR860 excitation/input/range,
sensitivity, time constant, and settle policy immediately before live preflight.

## Lab Checklist

- [ ] Regenerate the lab smoke bundle.
- [ ] Run the `measurement-parameter-audit` commands before per-recipe
      preflight.
- [ ] Confirm every audit prints `Hardware-ready: True`.
- [ ] Confirm the JSON outputs are written under `lab_smoke/`.
- [ ] Continue to hardware preflight only after all measurement-parameter audits
      pass.
