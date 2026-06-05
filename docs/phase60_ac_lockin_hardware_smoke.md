# Phase 60: Two-Terminal AC Lock-In Hardware Smoke

This phase enables the first real AC/lock-in hardware smoke path:

- Keithley 2450 acts as the conservative DC bias/source instrument.
- SR860 is read through the manual-backed lock-in driver.
- `ptm ac-lockin` now supports hardware execution after AC preflight and
  confirmation.

## Safety Boundary

Hardware output is enabled only after:

1. recipe and safety validation pass
2. `ptm ac-lockin-preflight` equivalent checks pass
3. the user confirms the hardware run, unless `--yes` is supplied

The runner turns the Keithley output off in normal completion, safety stop,
errors, and interruption. The SR860 is read-only in this phase.

## Smoke Recipe

Use:

```powershell
configs/recipes/ac_lockin_hardware_smoke.yaml
```

Edit the source and SR860 addresses before use.

## Lab Commands

```powershell
ptm list-resources
ptm ac-lockin-plan configs/recipes/ac_lockin_hardware_smoke.yaml
ptm ac-lockin-preflight configs/recipes/ac_lockin_hardware_smoke.yaml
ptm ac-lockin configs/recipes/ac_lockin_hardware_smoke.yaml --dry-run --summary --plot --report --fake-resistance-ohm 1000000 --fake-lockin-r-v 0.000002 --fake-lockin-phase-deg 30 --fake-noise-std 0
ptm ac-lockin configs/recipes/ac_lockin_hardware_smoke.yaml --progress --summary --plot --report
ptm ac-lockin-lab-smoke-intake data\raw\<run> --min-points 5 --min-abs-lockin-r-v <low> --max-abs-lockin-r-v <high> --json-output docs\ac_lockin_lab_smoke_intake.json
```

Use `--yes` only after the prompt path has already been tested.

## Expected Result

- `metadata.json` has `completed: true`
- `points.csv` includes source current and lock-in X/Y/R/theta columns
- `ac_lockin_plot.svg` and `ac_lockin_report.md` are written when requested
- Keithley output is off after the run
- SR860 communication is closed after the run
- `ptm ac-lockin-lab-smoke-intake` reports PASS before broader AC work

## Next Step

After the smoke test is verified on the lab laptop, keep the saved intake JSON
with the lab notebook. Do not broaden the AC sweep, change SR860 sensitivity, or
use a graphene device until the intake confirms source SMU readback, SR860
setting readback, output cleanup, Keithley NPLC/ranges/compliance, and lock-in
signal bounds.
