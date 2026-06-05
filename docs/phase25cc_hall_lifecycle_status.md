# Phase 25cc: Hall Package Lifecycle Status

Added a package-level lifecycle status command:

```powershell
ptm dual-gate-lockin-hall-suite-lifecycle-status data\hall_packages\<package> --json-output data\hall_packages\<package>\lifecycle_status.json
```

The command reports where a dual-gate lock-in Hall package is in the lab
workflow:

- `package_ready`: package manifest, recipes, runbook, ZIP, and audits are
  present.
- `ready_for_lab_handoff`: package handoff summary passed.
- `ready_for_analysis`: returned lab runs passed intake and the lab-return
  manifest is written.
- `analysis_written`: Hall analysis artifacts exist.
- `analysis_reviewed`: analysis review accepted the run set for next-scan
  decision.
- `next_scan_proposed`: a next-scan proposal has been written.

This is a read-only status layer. It does not replace the individual validators,
intake checks, Hall analysis, or proposal commands; it gives the lab notebook
one compact state report for the current package.

## NPLC Reminder

Keithley 2450 NPLC is already part of the recipe, driver configuration,
metadata readback, and hardware guards. Treat NPLC as a measurement condition:
it controls current integration time and should stay fixed when comparing Hall
scans unless the lab deliberately changes the noise/speed tradeoff and records
that change.

## Lab Checklist

- [ ] Run lifecycle status after package creation and handoff summary.
- [ ] Confirm lifecycle state is `ready_for_lab_handoff` before moving the
  package to the lab laptop.
- [ ] Run lifecycle status again after result intake and lab-return manifest.
- [ ] Confirm lifecycle state is `ready_for_analysis` before Hall analysis.
- [ ] Confirm every active Keithley block still has deliberate `nplc`,
  `voltage_range_v`, and `current_range_a` values before hardware acquisition.
