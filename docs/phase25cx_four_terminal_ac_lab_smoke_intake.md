# Phase 25cx: Four-Terminal AC Lab Smoke Intake Hardening

## Purpose

Four-terminal AC active output is guarded by approval flags and contact
topology. The saved run intake now verifies that this guard evidence survived
into `metadata.json` and agrees with the acquired points.

## What Changed

`ptm ac-lockin-lab-smoke-intake` is now geometry-aware:

- two-terminal AC smoke intake keeps the existing Keithley/SR860/output cleanup
  checks
- four-terminal AC smoke intake additionally requires:
  - `metadata.hardware_guard`
  - `hardware_guard.four_terminal_ac_allowed: true`
  - non-empty `hardware_guard.hardware_approval_note`
  - `hardware_guard.point_count` matching `points.csv`
  - `hardware_guard.point_count <= hardware_guard.max_hardware_points`
  - `lockin.voltage_input: a-b`
  - two excitation contacts and two SR860 voltage contacts
  - no overlap between excitation contacts and SR860 voltage contacts
  - guard topology snapshot matching recipe topology

The text and JSON outputs now include the hardware guard state, approval note,
point guard, lock-in voltage input, topology contacts, and Keithley NPLC/range
conditions.

## Lab Command

```powershell
ptm ac-lockin-lab-smoke-intake data\raw\<run> --min-points 3 --min-abs-lockin-r-v <low> --max-abs-lockin-r-v <high> --json-output docs\four_terminal_ac_lab_smoke_intake.json
```

## NPLC Reminder

The intake still requires saved Keithley source measurement conditions:
`configured_source_smu.nplc`, `voltage_range_v`, `current_range_a`, and
`current_compliance_a`. Treat NPLC as part of the measurement condition when
comparing graphene Hall-bar scans.

## Checklist

- [ ] Confirm the intake prints `AC lock-in lab smoke intake: PASS`.
- [ ] Confirm `Hardware guard required: True`.
- [ ] Confirm `Hardware guard present: True`.
- [ ] Confirm `Hardware guard accepted: True`.
- [ ] Confirm the guard point count matches the CSV row count.
- [ ] Confirm `Lock-in voltage input: a-b`.
- [ ] Confirm excitation and SR860 voltage contacts match the lab notebook.
- [ ] Confirm Keithley NPLC/ranges/compliance match the recipe.
- [ ] Do not broaden the scan until this intake passes.
