# Phase 25ag: Guarded Four-Terminal Lock-In Geometry

This phase opens four-terminal geometry for SR860 voltage-readout measurement
paths while keeping Keithley-only DC four-wire work blocked until its own
remote-sense runner exists.

## Scope

Allowed now:

- AC lock-in recipes with `measurement_geometry.method: four_terminal`,
  `terminal_count: 4`, `lockin.input_mode: voltage`, and
  `lockin.voltage_input: a-b`.
- Dual-gate lock-in Hall-bar recipes with the same differential SR860 voltage
  input plus explicit topology contacts.

Still blocked:

- Drain I-V four-terminal DC.
- Single-gate / dual-gate DC four-terminal.
- Keithley 2450 remote-sense / 4-wire mode.
- Pulse four-terminal hardware.

## Safety Rules

For four-terminal lock-in geometry, the SR860 must be used as a differential
voltage readout:

```yaml
measurement_geometry:
  method: four_terminal
  terminal_count: 4
lockin:
  input_mode: voltage
  voltage_input: a-b
```

For dual-gate Hall-bar lock-in recipes, topology must also declare separate
voltage and excitation contacts:

```yaml
topology:
  source_contact: S
  drain_contact: D
  lockin_input_contacts: [Vxx+, Vxx-]
  excitation_contacts: [S, D]
```

The safety gate rejects overlapping voltage/excitation contacts because that
would no longer be a clean four-terminal voltage readout.

## New Dry-Run Recipes

- `configs/recipes/ac_lockin_four_terminal_dry_run.yaml`
- `configs/recipes/dual_gate_lockin_four_terminal_dry_run.yaml`

Run them without hardware:

```powershell
ptm ac-lockin configs/recipes/ac_lockin_four_terminal_dry_run.yaml --dry-run --summary --plot --report --fake-noise-std 0
ptm dual-gate-lockin configs/recipes/dual_gate_lockin_four_terminal_dry_run.yaml --dry-run --summary --plot --report --gate-stats --fake-noise-std 0
```

## Lab Checklist

- Confirm SR860 input wiring corresponds to A-B differential voltage input.
- Confirm voltage probe contacts are not source/drain excitation contacts.
- Confirm the plan prints `four_terminal, 4-terminal` and `Lock-in voltage
  input: a-b`.
- Use dry-run artifacts first, then preflight, then a small smoke run.
