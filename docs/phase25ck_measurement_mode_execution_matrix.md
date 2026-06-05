# Phase 25ck: Measurement Mode Execution Matrix

This phase adds a hardware-facing execution matrix for the graphene Hall-bar
development path.

Command:

```powershell
ptm measurement-modes --verbose
ptm measurement-modes --json-output docs\measurement_modes.json
```

The matrix tracks these target modes:

- `two_terminal_dc`: Keithley 2450 Drain I-V, hardware verified.
- `four_terminal_dc`: planned Keithley 2450 4-probe / remote-sense DC path.
- `two_terminal_ac`: Keithley source bias plus SR860 readout, hardware-smoke
  ready after preflight.
- `four_terminal_ac`: SR860 differential voltage readout, dry-run and topology
  guarded.
- `hall_dual_gate_lockin`: two gate Keithleys plus SR860 Hall-suite workflow,
  dry-run/package workflow ready.

Each row records the measurement type, geometry, instruments, recipe examples,
plan/preflight/run commands, guarded parameters, safety gates, limitations, and
next measurement-focused step.

## Lab Checklist

- [ ] Run `ptm measurement-modes --verbose`.
- [ ] Confirm `two_terminal_dc` is `hardware_verified`.
- [ ] Confirm `four_terminal_dc` is still `planned`, not accidentally enabled.
- [ ] Confirm `two_terminal_ac` points to `ac_lockin_hardware_smoke.yaml`.
- [ ] Confirm `hall_dual_gate_lockin` lists gate NPLC, gate ranges,
  compliance, SR860 settings, condition audits, and chunk guards.
- [ ] Use the matrix to choose the next hardware-facing phase before adding
  convenience/UI features.
