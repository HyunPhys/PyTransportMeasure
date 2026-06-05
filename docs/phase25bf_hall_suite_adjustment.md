# Phase 25bf: Hall-Suite Full Acquisition Readiness

This phase adds suite-level recipe adjustment for the Hall-bar graphene
dual-gate lock-in workflow.

## What Changed

- Added `ptm dual-gate-lockin-hall-suite-adjust-recipes`.
- The command accepts an existing Vxx/+B Vxy/-B Vxy suite, plus optional 0B Vxy,
  and writes a new adjusted recipe set.
- It changes measurement parameters as a group:
  - gate1/gate2 Keithley NPLC, or one shared gate NPLC
  - gate1/gate2 gate settle time, or one shared gate settle time
  - SR860 sensitivity index
  - SR860 time constant index
  - SR860 settle time constants
  - SR860 read-settle override
- It preserves the gate grid, Hall topology, magnetic-field roles, contacts, and
  safety preset.
- It checks the input suite before writing and checks the adjusted suite after
  writing.
- It writes an adjustment review markdown with the updated measurement
  parameters and the required suite-check, suite-plan, chunk-plan, and preflight
  commands.

## Why This Matters

After the first checkpoint chunks, the lab may decide to increase Keithley NPLC,
increase gate settle time, or change SR860 sensitivity/time constant. Changing
only one recipe by hand can silently make Vxx/+B/-B/0B inconsistent. This command
makes the adjustment atomic at the suite level.

Keithley NPLC is treated as a core measurement parameter, not a minor driver
detail. It controls current integration time in power-line cycles and directly
sets the speed/noise tradeoff for gate leakage readback.

## Example

```powershell
ptm dual-gate-lockin-hall-suite-adjust-recipes configs\recipes\<suite>\<prefix>_vxx.yaml configs\recipes\<suite>\<prefix>_vxy_plus_b.yaml configs\recipes\<suite>\<prefix>_vxy_minus_b.yaml configs\recipes\<adjusted_suite> --zero-field-recipe configs\recipes\<suite>\<prefix>_vxy_zero_b.yaml --measurement-prefix <prefix_after_feedback> --gate-nplc 3 --gate-settle-s 0.4 --lockin-sensitivity-index 20 --lockin-time-constant-index 11 --lockin-read-settle-s 0.8 --adjustment-note "chunk feedback: reduce noise before full suite"
```

## Lab Checklist

- [ ] Run the original suite check before adjustment.
- [ ] Generate the adjusted suite as a group.
- [ ] Confirm the command writes four adjusted recipes and an adjustment review.
- [ ] Run the adjusted suite check and confirm PASS.
- [ ] Open the adjustment review and confirm NPLC, settle, SR860 sensitivity,
  SR860 time constant, and SR860 read-settle match the lab decision.
- [ ] Run preflight on each adjusted recipe before any hardware output.

## Verification

- `python -m pytest tests\test_hall_suite_template.py -q`
- `python -m pytransport.cli dual-gate-lockin-hall-suite-adjust-recipes --help`
