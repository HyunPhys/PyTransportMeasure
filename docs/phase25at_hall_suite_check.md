# Phase 25at: Hall-Bar Recipe Suite Consistency Check

## Goal

Validate a generated Hall-bar recipe suite before any hardware run.

The suite check is a hardware-free guard for Vxx, `+B` Vxy, `-B` Vxy, and
optional `0B` Vxy recipes. It catches YAML drift before the lab laptop enables
Keithley gate outputs.

## Command

```powershell
ptm dual-gate-lockin-hall-suite-check configs\recipes\<suite>\<prefix>_vxx.yaml configs\recipes\<suite>\<prefix>_vxy_plus_b.yaml configs\recipes\<suite>\<prefix>_vxy_minus_b.yaml --zero-field-recipe configs\recipes\<suite>\<prefix>_vxy_zero_b.yaml
```

## Checks

The command requires:

- Vxx recipe uses `voltage_probe_role: longitudinal`
- Hall recipes use `voltage_probe_role: hall`
- Vxx recipe declares `channel_length_m` and `channel_width_m`
- Hall recipes do not declare channel L/W
- `+B` and `-B` recipes have equal-magnitude opposite `magnetic_field_t`
- optional `0B` recipe has `magnetic_field_t: 0`
- gate1/gate2 instruments match across the suite
- SR860 settings match across the suite
- gate sweeps and point counts match across the suite
- shared topology fields, excitation path, and safety preset match

It warns, but does not fail, if Vxx and Vxy recipes use the same lock-in voltage
contacts.

## Hardware Boundary

This command only reads YAML recipe files. It does not list VISA resources,
probe instruments, configure SR860, or enable Keithley outputs.
