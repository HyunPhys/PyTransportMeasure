# Phase 25bs: Measurement Parameter Audit Expansion

## Summary

This phase adds a reusable Keithley source-block parameter audit for hardware
recipes. The audit is hardware-free and checks the recipe-level measurement
condition before any VISA communication or output enable.

## New API

- `audit_smu_hardware_parameters(recipe)`
- `smu_hardware_parameter_audit_to_dict(audits)`
- `format_smu_hardware_parameter_audit(audits)`

The audit covers every SMU role present in a recipe:

- `instrument`
- `source`
- `drain`
- `gate`
- `gate1`
- `gate2`

## New CLI

```powershell
ptm keithley-parameter-audit <measurement_type> <recipe> --json-output docs\<sample>_keithley_audit.json
```

Examples:

```powershell
ptm keithley-parameter-audit drain_iv configs\recipes\drain_iv.yaml
ptm keithley-parameter-audit dual_gate_lockin_sweep configs\recipes\dual_gate_lockin_four_terminal_dry_run.yaml --json-output docs\dual_gate_lockin_keithley_audit.json
```

## What It Reports

- Keithley role
- instrument id and VISA address
- terminal selection
- voltage range
- current range
- NPLC
- source delay
- current compliance
- missing required hardware parameters

For Keithley 2450 hardware output, the required recipe fields remain:

- `nplc`
- `voltage_range_v`
- `current_range_a`

## Why

NPLC, ranges, compliance, terminal selection, and source delay are measurement
conditions. For Hall-bar graphene scans, changing them between Vxx, +B Vxy, -B
Vxy, or the next approved package can change the physical interpretation of the
data. This audit gives the lab a compact text and JSON artifact to compare
before hardware acquisition.

## Lab Checklist

- [ ] Run the Keithley parameter audit before preflight on the lab laptop.
- [ ] Save `--json-output` with the package or notebook artifacts.
- [ ] Confirm every active Keithley role reports `PASS`.
- [ ] Confirm NPLC/range/compliance/source-delay match the intended lab
      notebook settings.
- [ ] If any role reports `MISSING`, edit the recipe before hardware preflight.
