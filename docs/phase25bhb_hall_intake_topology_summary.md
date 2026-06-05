# Phase 25bhb: Hall Intake Topology Summary

## Summary

This phase adds Hall-bar contact topology summaries directly to the Hall-suite
result-intake artifacts.

`ptm dual-gate-lockin-hall-suite-intake` now writes each returned run's topology
under `result_intake.json -> runs -> <role> -> topology` and prints a
`Returned Run Topology` table in `result_intake_report.md`.

## Recorded Fields

Each run records:

- voltage-probe role
- magnetic field
- excitation contacts
- SR860 voltage contacts
- channel length and width
- topology layout

## Why This Matters

Condition snapshot and drift audits still provide the deeper pre-analysis gate,
but intake is the first returned-package checkpoint. Seeing Vxx/Vxy contacts at
intake time helps catch run-folder swaps and contact-label mistakes before
analysis commands are even considered.

## Lab Checklist

- [ ] Run `ptm dual-gate-lockin-hall-suite-intake ...`.
- [ ] Open `result_intake_report.md`.
- [ ] Confirm `Returned Run Topology` lists the expected Vxx and Vxy roles.
- [ ] Confirm `result_intake.json` contains `runs.<role>.topology`.
- [ ] Continue to condition snapshot/drift only after the intake topology table
  agrees with the lab notebook.
