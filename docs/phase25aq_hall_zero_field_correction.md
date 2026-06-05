# Phase 25aq: Hall Zero-Field Offset Correction

## Goal

Add a saved-run analysis step for Hall voltage offset subtraction without
changing hardware-control behavior.

This is useful when a Hall Vxy run at finite magnetic field has a matching
`B=0` run that captures contact misalignment or lock-in voltage offset over the
same gate grid.

## Command

```powershell
ptm dual-gate-lockin-hall-zero-correct data\raw\<field_B_run> data\raw\<zero_B_run> --output-dir data\analysis\<hall_zero_corrected_folder>
```

The command also accepts `--value-column` with the same options as
`dual-gate-lockin-hall-antisym`.

## Required Inputs

- Both inputs must be completed `dual_gate_lockin_sweep` runs.
- Both inputs must have `voltage_probe_role: hall`.
- The field run must have nonzero `magnetic_field_t`.
- The zero-field run must have `magnetic_field_t: 0`.
- Gate grids must match exactly.

## Outputs

- `hall_zero_corrected.csv`
- `hall_zero_corrected_report.md`
- `hall_zero_corrected_metadata.json`

CSV columns include:

- `field_resistance_ohm`
- `zero_field_resistance_ohm`
- `hall_zero_corrected_resistance_ohm`
- `hall_carrier_density_per_m2`

## Model

```text
Rxy_corrected = Rxy(B) - Rxy(0)
n_2d = B / (e * Rxy_corrected)
```

Prefer antisymmetrization when matched `+B` and `-B` runs are available. Use this
zero-field correction path when the saved measurement set contains a reliable
`B=0` Hall offset run but does not yet have both magnetic-field polarities.

## Hardware Boundary

No instrument is configured or enabled by this phase. It only reads saved
artifacts and writes derived analysis artifacts. Hardware safety remains governed
by the dual-gate lock-in runner, acceptance audit, SR860 runtime gate, and
Keithley range/NPLC guards.
