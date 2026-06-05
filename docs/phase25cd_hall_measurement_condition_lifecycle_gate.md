# Phase 25cd: Hall Measurement-Condition Lifecycle Gate

Strengthened the Hall package lifecycle status so it reports measurement
condition readiness directly:

```powershell
ptm dual-gate-lockin-hall-suite-lifecycle-status data\hall_packages\<package>
```

The lifecycle report now includes:

- `Measurement-condition audits`
- `Keithley parameter audits`
- `SR860 setting audits`

The package is not considered `ready_for_lab_handoff` or `ready_for_analysis`
unless those audit stages pass. This prevents a stale handoff summary or
returned-run manifest from hiding a broken measurement-condition record.

## Measurement Parameters

Keithley NPLC, voltage range, current range, compliance, terminal selection,
source delay, and SR860 settings are part of the measurement condition. They
are not GUI details. For Hall-bar graphene scans, changing these values changes
the scan's noise, speed, and comparability.

## Lab Checklist

- [ ] Run lifecycle status before moving a package to the lab laptop.
- [ ] Confirm `Measurement conditions ready: True`.
- [ ] Confirm `Measurement-condition audits`, `Keithley parameter audits`, and
  `SR860 setting audits` are PASS.
- [ ] If lifecycle state is `measurement_condition_review`, regenerate or repair
  the package before hardware acquisition.
- [ ] Confirm every active Keithley recipe block has deliberate `nplc`,
  `voltage_range_v`, and `current_range_a` values.
