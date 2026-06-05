# Phase 25e: Dual-Gate Lock-In Hardware Preflight

This phase adds a read-only hardware-readiness gate for the likely Hall bar
graphene path: two Keithley 2450 instruments bias the two gates, and one SR860
lock-in records source-drain response.

## Command

```powershell
ptm dual-gate-lockin-preflight configs/recipes/dual_gate_lockin_dry_run.yaml
```

The preflight checks:

- recipe safety validation
- visible VISA resources
- gate1 Keithley address
- gate2 Keithley address
- SR860 address
- all three addresses are distinct
- read-only Keithley probes for gate1 and gate2
- read-only SR860 probe

## Hardware Policy

`ptm dual-gate-lockin` without `--dry-run` now prints the preflight report before
returning the existing hardware-block message. It still does not enable gate
output.

The active hardware sweep remains blocked until SR860 excitation and Hall bar
source-drain wiring are explicitly smoke-tested.

## Expected Lab-Laptop Result

- `Validation OK: True`
- `Gate1/gate2/lock-in addresses distinct: True`
- gate1 address found and probe OK
- gate2 address found and probe OK
- SR860 address found and probe OK
- `Dual-gate lock-in preflight OK: True`
