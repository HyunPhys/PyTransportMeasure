# Phase 25dab: SR860 Measurement Parameter Audit

## Summary

This phase expands hardware-free measurement-condition auditing beyond
Keithley 2450 source blocks. The new combined audit reports both:

- Keithley SMU conditions: voltage range, current range, NPLC, source delay,
  terminal, and compliance.
- SR860 lock-in conditions: reference, excitation amplitude, input wiring,
  input range, sensitivity, time constant, filter slope, synchronous filter,
  and read-settle policy.

The existing `ptm keithley-parameter-audit` command remains available for
Keithley-only checks.

## New CLI

```powershell
ptm measurement-parameter-audit <measurement_type> <recipe>
ptm measurement-parameter-audit dual_gate_lockin_sweep configs\recipes\dual_gate_lockin_four_terminal_dry_run.yaml --json-output docs\dual_gate_lockin_measurement_audit.json
```

The command exits with:

- `0` when every active Keithley and SR860 role is hardware-ready.
- `2` when required measurement conditions are missing.

## SR860 Hardware-Ready Policy

For SR860 hardware runs, the recipe should explicitly declare:

- `reference_source`
- `reference_frequency_hz`
- `sine_output_amplitude_v`
- `input_mode`
- `voltage_input`
- `input_coupling`
- `input_grounding`
- `voltage_input_range_v`
- `sensitivity_index`
- `time_constant_index`
- `filter_slope_db_per_oct`
- `synchronous_filter`

The recipe must also define a positive settle policy:

- `read_settle_s > 0`, or
- `time_constant_index` with `settle_time_constants > 0`

## Why

For lock-in transport measurements, SR860 settings are measurement conditions,
not UI details. Changing sensitivity, input range, time constant, excitation
amplitude, or input wiring can change noise floor, phase, overload behavior,
and the physical interpretation of Hall-bar data. The combined audit gives a
single text and JSON artifact to attach to lab handoffs before active scans.

## Lab Checklist

- [ ] Run `ptm measurement-parameter-audit` before lock-in hardware preflight.
- [ ] Save `--json-output` next to the Hall package or lab notebook artifacts.
- [ ] Confirm the SMU section reports `PASS` for all active Keithley roles.
- [ ] Confirm the SR860 section reports `PASS`.
- [ ] Confirm SR860 frequency, sine amplitude, input wiring, range,
      sensitivity, time constant, filter slope, and settle policy match the
      lab notebook.
- [ ] If any role reports `MISSING`, edit the recipe before hardware preflight.
