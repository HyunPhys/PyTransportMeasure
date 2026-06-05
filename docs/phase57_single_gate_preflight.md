# Phase 57: Single-Gate / Two-SMU Preflight

This phase adds a hardware-readiness gate for the two-Keithley single-gate
workflow. It does not enable new output behavior; it checks the recipe, safety
preset, VISA resources, and both Keithley probes before a two-SMU hardware run.

## Why

The long-term measurement target is Hall-bar graphene transport with dual-gate
scans and DC/AC, two-terminal/four-terminal modes. Before adding dual-gate or
SR860 hardware acquisition, the code needs a reliable multi-instrument preflight
path that can block unsafe or ambiguous hardware states.

## Commands

```powershell
ptm list-resources
ptm single-gate-plan configs/recipes/single_gate_hardware_smoke.yaml
ptm single-gate-preflight configs/recipes/single_gate_hardware_smoke.yaml
ptm single-gate configs/recipes/single_gate_hardware_smoke.yaml --dry-run --summary --plot --report --gate-stats --fake-channel-resistance-ohm 1000000 --fake-gate-leak-resistance-ohm 1000000000 --fake-noise-std-a 0
```

Only after the preflight and dry-run pass should the hardware command be used:

```powershell
ptm single-gate configs/recipes/single_gate_hardware_smoke.yaml --progress --summary --plot --report --gate-stats
```

## Expected Preflight

- `Drain/gate addresses distinct: True`
- drain `address found: True`
- gate `address found: True`
- both probes report Keithley 2450 identity and `0,"No error"`
- `Single-gate preflight OK: True`

## Notes For Next Phases

- SR860 work must be based on `SR860m.pdf` in the project root.
- Four-terminal mode stays TODO until the Keithley sense-mode command sequence
  and metadata representation are implemented deliberately.
- Dual-gate scan should compose verified inner measurement methods instead of
  duplicating low-level instrument logic.
