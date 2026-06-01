# Phase 19 - Single-Gate Hardware Smoke-Test Preparation

This phase prepares the first real two-SMU single-gate smoke test without
changing the verified hardware command sequence beyond the existing single-gate
runner.

## What Changed

- Added conservative safety preset:
  - `configs/safety/single_gate_first_contact.yaml`
- Added conservative hardware smoke recipe:
  - `configs/recipes/single_gate_hardware_smoke.yaml`
- Added tests that confirm:
  - the hardware smoke recipe loads and plans correctly
  - drain and gate fake SMU outputs are off after a completed run
  - drain and gate fake SMU outputs are off after a compliance stop

## Hardware Smoke Recipe

The smoke recipe is intentionally small:

- Gate sweep: `-0.1 V -> 0.1 V`, 3 points
- Drain sweep: `-0.05 V -> 0.05 V`, 5 points
- Total points: 15
- Gate compliance: `1e-9 A`
- Drain compliance: `1e-7 A`
- Safety voltage limit: `0.2 V`
- Safety current limit: `1e-7 A`

Edit the drain and gate VISA addresses before running on hardware:

```yaml
drain_instrument:
  address: GPIB0::2::INSTR
gate_instrument:
  address: GPIB0::3::INSTR
```

The two addresses must be different.

## Required Pre-Hardware Checklist

- [ ] Confirm both Keithleys are physically connected.
- [ ] Confirm both Keithleys are in SCPI command mode.
- [ ] Confirm both VISA resources are visible.
  ```powershell
  ptm list-resources
  ```
- [ ] Edit `configs/recipes/single_gate_hardware_smoke.yaml` so drain and gate
  addresses match the actual instruments.
- [ ] Confirm drain and gate addresses are different.
- [ ] Confirm terminals are correct, usually `FRONT` for the current lab setup.
- [ ] Inspect the exact plan.
  ```powershell
  ptm single-gate-plan configs/recipes/single_gate_hardware_smoke.yaml
  ```
- [ ] Dry-run the same recipe first.
  ```powershell
  ptm single-gate configs/recipes/single_gate_hardware_smoke.yaml --dry-run --summary --plot --report --gate-stats --fake-channel-resistance-ohm 1000000 --fake-gate-leak-resistance-ohm 1000000000 --fake-noise-std-a 0
  ```
- [ ] Run hardware without `--yes` the first time, so the confirmation prompt is
  still active.
  ```powershell
  ptm single-gate configs/recipes/single_gate_hardware_smoke.yaml --progress --summary --plot --report --gate-stats
  ```
- [ ] Confirm both Keithley outputs are off after normal completion, safety stop,
  or user interrupt.

## Current Boundary

This phase prepares the smoke test. It does not claim that the two-Keithley
single-gate hardware workflow has been lab-verified yet. Hardware verification
should be marked complete only after the checklist above passes on the actual
instruments.

