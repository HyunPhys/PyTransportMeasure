# Phase 25dah: SR860 Configuration Command Review

## Summary

This phase adds a hardware-free SR860 command review:

```powershell
ptm sr860-command-review dual_gate_lockin_sweep configs\recipes\dual_gate_lockin_four_terminal_dry_run.yaml --json-output docs\sr860_command_review.json
```

The command converts recipe SR860 settings into explicit SCPI write/readback
pairs. It does not communicate with VISA and does not write to the SR860.

## Scope

The review covers:

- `RSRC`: reference source
- `FREQ`: internal reference frequency
- `SLVL`: sine output amplitude
- `IVMD`: voltage/current input mode
- `ISRC`: voltage input A or A-B
- `ICPL`: input coupling
- `IGND`: input grounding
- `IRNG`: voltage input range
- `SCAL`: sensitivity index
- `OFLT`: time-constant index
- `OFSL`: output filter slope
- `SYNC`: synchronous filter state

The output also embeds the existing SR860 hardware-parameter audit, so the
review returns nonzero when required lock-in measurement conditions are missing.

## Why This Matters

Current runners intentionally do not write SR860 settings. Before adding an
active configure path, the lab needs a reviewable command contract that maps
recipe fields to exact SCPI commands and expected readbacks. This keeps future
SR860 writes auditable and makes accidental sensitivity/time-constant/input
changes easier to catch.

## Lab Checklist

- [ ] Run `ptm sr860-command-review ...` for each AC/lock-in hardware recipe.
- [ ] Save the JSON output with preflight notes or the Hall package.
- [ ] Confirm the command list matches the intended SR860 front-panel settings.
- [ ] Do not use an active SR860 configure path until the command review and
  live SR860 readback agree.
