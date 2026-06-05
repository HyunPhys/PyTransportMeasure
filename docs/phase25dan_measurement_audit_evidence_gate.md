# Phase 25dan: Measurement Audit Evidence Gate

## Summary

This phase adds a hardware-free evidence check for saved measurement-parameter
audit JSON files. The check recomputes the current recipe audit and compares it
against the saved JSON before hardware preflight.

It catches recipe drift in measurement conditions such as:

- Keithley 2450 voltage range
- Keithley 2450 current range
- Keithley 2450 NPLC
- Keithley current compliance
- Keithley source delay
- SR860 reference/input/range/sensitivity/time-constant/filter/settle settings

## Commands

Generate the audit:

```powershell
ptm measurement-parameter-audit dual_gate_lockin_sweep configs\recipes\dual_gate_lockin_limited_active.yaml --json-output docs\dual_gate_measurement_audit.json
```

Check that the saved audit still matches the recipe:

```powershell
ptm measurement-parameter-audit-check dual_gate_lockin_sweep configs\recipes\dual_gate_lockin_limited_active.yaml docs\dual_gate_measurement_audit.json
```

Require the saved audit before hardware preflight:

```powershell
ptm dual-gate-lockin-preflight configs\recipes\dual_gate_lockin_limited_active.yaml --measurement-audit-json docs\dual_gate_measurement_audit.json
```

Guarded lock-in hardware commands also accept `--measurement-audit-json`.

## Lab Checklist

- [ ] Generate a fresh measurement-parameter audit JSON after editing a recipe.
- [ ] Confirm the audit reports `Hardware-ready: True`.
- [ ] Run `measurement-parameter-audit-check` before hardware preflight.
- [ ] Pass the same `--measurement-audit-json` to guarded hardware commands.
- [ ] If the evidence check fails, review NPLC/ranges/compliance/SR860 settings
      and regenerate the audit only after confirming the recipe change was
      intentional.
