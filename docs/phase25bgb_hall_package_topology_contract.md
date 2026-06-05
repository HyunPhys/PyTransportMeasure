# Phase 25bgb: Hall Package Topology Contract

## Summary

This phase records the expected Hall-bar topology directly in Hall-suite
acquisition packages.

`ptm dual-gate-lockin-hall-suite-package` now writes:

- `package_manifest.json -> topology_contract`
- a `Topology Contract` table in `acquisition_runbook.md`

The contract is generated from the packaged Vxx/+B/-B/0B recipes and records
the voltage-probe role, magnetic field, excitation contacts, SR860 voltage
contacts, channel geometry, and topology layout.
It is intentionally colocated with the existing Keithley and SR860
measurement-condition audits. Keithley NPLC, voltage range, current range,
compliance, and source delay remain explicit run conditions rather than hidden
driver defaults.

## Why This Matters

The package is the lab-laptop handoff contract. It should state not only the
Keithley/SR860 measurement parameters, but also which Hall-bar contacts define
Vxx and Vxy. This lets the operator compare the wiring plan before preflight,
then compare returned run topology at intake and drift-audit time.

## Lab Checklist

- [ ] Open `acquisition_runbook.md` before lab preflight.
- [ ] Confirm `Topology Contract` matches the device wiring plan.
- [ ] Confirm `package_manifest.json` has `topology_contract`.
- [ ] Do not run hardware if the contract has stale Vxx/Vxy contact labels.
- [ ] If contacts changed, regenerate the recipe suite/package rather than
  editing returned metadata by hand.
