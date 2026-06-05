# Phase 25ch: Hall Condition Snapshot Lifecycle Integration

The Hall package lifecycle status now includes the run condition snapshot
artifact:

```powershell
ptm dual-gate-lockin-hall-suite-lifecycle-status data\hall_packages\<package>
```

New lifecycle stage:

- `Run condition snapshot`

After result intake, lifecycle state becomes `condition_snapshot_pending` until
`condition_snapshot.json` exists and contains returned run rows. After the
snapshot is written, lifecycle can advance to `condition_drift_pending`, then
to `ready_for_analysis` once drift and lab-return manifest also pass.

`ready_for_analysis` now requires:

- measurement-condition audits PASS
- result intake PASS
- run condition snapshot present
- acquisition-condition drift PASS
- lab-return manifest PASS

The lab-return manifest now records the intake, condition snapshot, and
condition drift artifact paths together.

## Lab Checklist

- [ ] Run result intake.
- [ ] Run `ptm dual-gate-lockin-hall-suite-condition-snapshot <package>`.
- [ ] Run `ptm dual-gate-lockin-hall-suite-condition-drift <package>`.
- [ ] Write the lab-return manifest.
- [ ] Run lifecycle status and confirm `Run condition snapshot` and
  `Acquisition-condition drift` are PASS.
