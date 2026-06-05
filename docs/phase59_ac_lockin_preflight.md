# Phase 59: AC Lock-In Two-Instrument Preflight

This phase adds a hardware-readiness gate for `ac_lockin_sweep` recipes without
enabling AC hardware acquisition.

## Scope

`ptm ac-lockin-preflight` checks:

- recipe schema and safety limits
- Keithley source VISA address
- Keithley source probe
- SR860 VISA address
- SR860 probe using the manual-backed read-only command subset
- source and lock-in addresses are distinct

The real `ptm ac-lockin` hardware runner remains blocked. If run without
`--dry-run`, it prints the AC preflight report first and then exits before
enabling any source output.

## Commands

```powershell
ptm list-resources
ptm ac-lockin-plan configs/recipes/ac_lockin_dry_run.yaml
ptm ac-lockin-preflight configs/recipes/ac_lockin_dry_run.yaml
ptm ac-lockin configs/recipes/ac_lockin_dry_run.yaml --dry-run --summary --plot --report --fake-resistance-ohm 1000000 --fake-lockin-r-v 0.000002 --fake-lockin-phase-deg 30 --fake-noise-std 0
```

Expected preflight:

- `Validation OK: True`
- `Source/lock-in addresses distinct: True`
- source `address found: True`
- lock-in `address found: True`
- SR860 probe includes `error_status: 0`
- `AC lock-in preflight OK: True`

## Next Step

After this passes on the lab laptop, the next measurement phase can add a
conservative two-terminal AC hardware smoke runner that uses the verified
Keithley source configuration and SR860 `read_channels()` primitive.
