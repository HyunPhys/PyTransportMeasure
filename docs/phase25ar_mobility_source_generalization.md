# Phase 25ar: Mobility Source Generalization

## Goal

Make mobility extraction independent of the specific Hall-density correction
path. The same mobility command can now consume either:

- `hall_antisym.csv` from matched `+B` and `-B` Hall runs
- `hall_zero_corrected.csv` from finite-field Hall data minus a `B=0` offset run

This keeps the longitudinal Vxx mobility step stable while the lab measurement
set may vary by magnet-time availability.

## Command

```powershell
ptm dual-gate-lockin-hall-mobility data\analysis\<hall_density_folder> data\raw\<longitudinal_Vxx_run> --output-dir data\analysis\<hall_mobility_folder>
```

`hall_density_folder` can contain either supported CSV. Passing the CSV path
directly also works.

## Output Additions

`hall_mobility.csv` now records source provenance:

- `hall_source_kind`: `antisym` or `zero_corrected`
- `hall_source_resistance_ohm`: the Hall resistance used for density
- `hall_antisym_resistance_ohm`: populated only for antisym inputs
- `hall_zero_corrected_resistance_ohm`: populated only for zero-corrected inputs

The metadata also records:

- `hall_density_csv`
- `hall_density_source_kind`
- `hall_antisym_csv` when applicable
- `hall_zero_corrected_csv` when applicable

## Hardware Boundary

This is still saved-artifact analysis only. It does not configure SR860 or
Keithley instruments and does not relax any active-run safety gate.
