# Phase 25ce: Hall Acquisition-Condition Drift Guard

Added a returned-run drift audit:

```powershell
ptm dual-gate-lockin-hall-suite-condition-drift data\hall_packages\<package>
```

The audit reads the package manifest, `result_intake.json`, and returned run
metadata. It compares the packaged measurement conditions against the run's
saved recipe snapshot and configured instrument metadata.

Checked conditions include:

- Keithley gate1/gate2 `nplc`
- Keithley voltage/current ranges
- Keithley current compliance
- Keithley terminal and source-delay settings
- SR860 expected settings and lock-in timing fields
- saved Keithley/SR860 readback mismatch flags

`ptm dual-gate-lockin-hall-suite-analyze` now runs the same drift guard
internally and refuses analysis when drift is detected. This keeps repeated
Hall-bar graphene scans comparable across lab-laptop runs.

## Lab Checklist

- [ ] Run result intake first and confirm PASS.
- [ ] Run `ptm dual-gate-lockin-hall-suite-condition-drift <package>`.
- [ ] Confirm the report status is PASS and issues are `none`.
- [ ] If the audit fails, do not run Hall analysis. Regenerate the package or
  repeat the run with the intended Keithley/SR860 settings.
- [ ] Treat NPLC changes as real measurement-condition changes, not a harmless
  run-time tweak.
