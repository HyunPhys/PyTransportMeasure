# Phase 25dag: Recipe Directory Measurement Parameter Audit

## Summary

This phase adds a hardware-free recipe-folder audit:

```powershell
ptm measurement-parameter-audit-dir configs\recipes --json-output docs\recipe_parameter_audit.json
```

The command scans YAML recipes, infers each measurement type, loads the matching
recipe schema, and reuses the existing measurement-parameter audit policy.

## Scope

The directory audit reports:

- Keithley 2450 NPLC, voltage range, current range, source delay, compliance
- SR860 reference, excitation amplitude, input wiring/range, sensitivity, time
  constant, filter slope, synchronous filter, and settle policy
- recipe load/schema errors
- PASS/FAIL status for every recipe file

It does not communicate with VISA or enable output.

## Notes

Dry-run skeleton recipes may intentionally fail hardware readiness if they omit
SR860 settle policy or other active-run parameters. That is useful: the audit
shows which files are safe to treat as hardware-ready and which are only
simulation examples.

The starter Drain I-V template now includes `instrument.nplc: 1.0`, so copied
two-terminal DC recipes keep NPLC explicit from the beginning.

## Lab Checklist

- [ ] Run `ptm measurement-parameter-audit-dir <recipe_folder>` before moving a
  recipe folder to the lab laptop.
- [ ] Save `--json-output` with the lab notebook or handoff package.
- [ ] Confirm every hardware recipe reports `Hardware-ready: True`.
- [ ] Treat any missing Keithley `nplc`, voltage range, current range, or SR860
  settle policy as a recipe-edit task before preflight.
