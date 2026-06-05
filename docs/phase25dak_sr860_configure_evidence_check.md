# Phase 25dak: SR860 Configure Evidence Check

## Summary

This phase adds a hardware-free checker for saved SR860 configure transcripts:

```powershell
ptm sr860-configure-check dual_gate_lockin_sweep configs\recipes\dual_gate_lockin_four_terminal_dry_run.yaml docs\sr860_configure.json --json-output docs\sr860_configure_check.json
```

The checker compares the saved configure JSON against the current recipe. It
does not communicate with VISA and does not write instrument settings.

## What It Verifies

- the JSON is a `pytransport.sr860_configure.v1` transcript
- the configure command reported `completed: true`
- the embedded command review was hardware-ready
- the embedded command list still matches the current recipe
- the write/readback transcript has one matched step per expected command
- each actual readback still matches the expected command readback value

## Why This Matters

SR860 settings affect the measurement condition directly: reference source,
frequency, sine amplitude, input wiring/range, sensitivity, time constant,
filter slope, and synchronous filter. A saved configure JSON should not be used
as lab evidence after the recipe has changed. This checker catches that drift
before live preflight or active Keithley output.

## Lab Checklist

- [ ] Run `ptm sr860-command-review ...`.
- [ ] Run guarded `ptm sr860-configure ... --json-output docs\sr860_configure.json`.
- [ ] Run `ptm sr860-configure-check ... docs\sr860_configure.json`.
- [ ] Continue to lock-in preflight only when the check reports `OK: True`.
- [ ] If it reports `OK: False`, treat the recipe/configure pair as stale and
      regenerate the evidence.
