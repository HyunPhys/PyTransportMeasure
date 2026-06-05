# Phase 25ap: Hall Mobility Extraction Analysis

## Goal

Connect the Hall-bar analysis chain from measured lock-in artifacts to mobility
maps without adding new hardware-control behavior.

This phase combines:

- a Hall density artifact from either matched `+B`/`-B` Vxy runs or a
  finite-field Vxy run corrected by a `B=0` offset run
- a completed longitudinal Vxx dual-gate lock-in run with sheet conductivity

The result is a gate-grid mobility table and report.

## Command

```powershell
ptm dual-gate-lockin-hall-mobility data\analysis\<hall_density_folder> data\raw\<longitudinal_Vxx_run> --output-dir data\analysis\<hall_mobility_folder>
```

The first argument can be a folder containing `hall_antisym.csv`, a folder
containing `hall_zero_corrected.csv`, or either CSV path directly.

## Required Inputs

- `hall_antisym.csv` or `hall_zero_corrected.csv` with matched
  `gate1_voltage_v` and `gate2_voltage_v` points and
  `hall_carrier_density_per_m2`.
- A completed `dual_gate_lockin_sweep` longitudinal run.
- The longitudinal metadata must contain `voltage_probe_role: longitudinal`.
- The longitudinal points must contain
  `lockin_sheet_conductivity_s_per_sq`.

## Outputs

- `hall_mobility.csv`
- `hall_mobility_report.md`
- `hall_mobility_metadata.json`

CSV columns include:

- `hall_carrier_density_per_m2`
- `hall_source_kind`
- `hall_source_resistance_ohm`
- `longitudinal_sheet_conductivity_s_per_sq`
- `longitudinal_sheet_resistance_ohm_per_sq`
- `mobility_signed_m2_per_v_s`
- `mobility_magnitude_m2_per_v_s`
- `mobility_magnitude_cm2_per_v_s`

## Model

The signed mobility follows the Hall density sign convention:

```text
mu_signed = sigma_sheet / (e * n_2d)
```

The lab-facing magnitude is:

```text
|mu| = |sigma_sheet| / (e * |n_2d|)
```

and is also written in `cm^2/V/s`.

## Hardware Boundary

This phase does not configure or enable any instrument. It is deliberately an
artifact analysis step so the mobility workflow can be checked with dry-run or
previously saved lab data before broader dual-gate scans are attempted.

For every hardware run that feeds this analysis, Keithley 2450 source blocks
must still declare the intended `voltage_range_v`, `current_range_a`, and
`nplc`. NPLC remains a measurement condition because it controls current
integration time and therefore the noise/speed tradeoff.
