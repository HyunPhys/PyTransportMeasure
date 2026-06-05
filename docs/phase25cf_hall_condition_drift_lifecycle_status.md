# Phase 25cf: Hall Condition Drift In Lifecycle Status

The Hall package lifecycle status now includes the returned-run
acquisition-condition drift artifact:

```powershell
ptm dual-gate-lockin-hall-suite-lifecycle-status data\hall_packages\<package>
```

New lifecycle stage:

- `Acquisition-condition drift`

After result intake, lifecycle state becomes `condition_drift_pending` until
`condition_drift.json` exists and passes. If the drift report exists but fails,
state becomes `acquisition_condition_drift`.

`ready_for_analysis` now requires all of:

- measurement-condition audits PASS
- result intake PASS
- acquisition-condition drift PASS
- lab-return manifest PASS

This lets the lab notebook status table block Hall analysis and next-scan
decisions when returned metadata no longer matches the packaged Keithley/SR860
measurement conditions.

## Lab Checklist

- [ ] Run result intake.
- [ ] Run `ptm dual-gate-lockin-hall-suite-condition-drift <package>`.
- [ ] Run lifecycle status.
- [ ] Confirm `Acquisition-condition drift` is PASS.
- [ ] Confirm lifecycle state is `ready_for_analysis` before Hall analysis.
