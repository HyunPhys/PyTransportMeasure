# Phase 25f: Dual-Gate Lock-In Topology Schema

This phase makes the Hall-bar wiring assumption explicit in dual-gate lock-in
recipes.

## Added Requirement

`dual_gate_lockin_sweep` recipes now require a `topology` block. It records:

- Hall-bar layout
- gate1 and gate2 physical roles
- source and drain contact labels
- lock-in input mode and contacts
- excitation source
- excitation contacts
- excitation amplitude
- optional current-bias resistor
- wiring notes

## Why

A dual-gate lock-in scan cannot be interpreted from gate voltages and lock-in
readout alone. The source-drain excitation path, voltage probe contacts, and
gate roles must be captured before hardware sweeps are enabled.

## Hardware Policy

This phase still does not enable dual-gate lock-in hardware output. The plan and
preflight commands now print the topology, so the operator can compare the
recipe against the actual Hall-bar wiring on the lab laptop.

## Lab-Laptop Check

```powershell
ptm dual-gate-lockin-plan configs/recipes/dual_gate_lockin_dry_run.yaml
ptm dual-gate-lockin-preflight configs/recipes/dual_gate_lockin_dry_run.yaml
```

Confirm the `Topology` section matches the real wiring before any future active
hardware sweep phase.
