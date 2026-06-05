# Phase 25daf: Hall Lab Smoke Audit Lifecycle Integration

## Summary

This phase connects the lab-smoke measurement-parameter audit collector to the
Hall handoff and lifecycle reports.

The handoff command now runs the package measurement-parameter audit bundle and
records its result beside the package validation, lab smoke checklist, and
hardware command review:

```powershell
ptm dual-gate-lockin-hall-suite-handoff-summary data\hall_packages\<package> --overwrite
```

The lifecycle and workflow status commands now show a dedicated stage:

- `Lab smoke measurement-parameter audits`

That stage passes when `measurement_parameter_audits.json` exists, contains at
least one recipe audit, and reports `ok_for_hardware: true` for the combined
Keithley/SR860 parameter checks.

## Why This Matters

Keithley settings such as NPLC, source range, sense range, compliance, and
source delay are measurement parameters, not cosmetic runtime details. SR860
reference, input wiring, sensitivity, time constant, filter slope, and settle
policy are similarly part of the measurement condition.

By surfacing the lab-smoke audit bundle in lifecycle status, the package makes
those conditions visible before active Hall scans and again when preparing the
lab notebook handoff.

## Lab Checklist

- [ ] Generate or refresh the lab smoke audit bundle.
- [ ] Run `ptm dual-gate-lockin-hall-suite-lab-smoke-audits ... --overwrite`
  or run the handoff summary command, which writes a handoff-local audit copy.
- [ ] Confirm `measurement_parameter_audits.md` reports
  `Hardware-ready: True`.
- [ ] Run lifecycle status.
- [ ] Confirm `Lab smoke parameters ready: True`.
- [ ] Confirm the `Lab smoke measurement-parameter audits` stage is PASS before
  moving to active hardware preflight.
