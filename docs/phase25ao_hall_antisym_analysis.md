# Phase 25ao: Hall Antisymmetrization Analysis

This phase adds a saved-run analysis command for paired `+B` and `-B`
dual-gate lock-in Hall measurements.

## Command

```powershell
ptm dual-gate-lockin-hall-antisym data\raw\<plus_B_run> data\raw\<minus_B_run> --output-dir data\analysis\<hall_antisym_folder>
```

The command writes:

- `hall_antisym.csv`
- `hall_antisym_report.md`
- `hall_antisym_metadata.json`

## Model

The default value column is `lockin_x_v`, because signed in-phase voltage is
more useful for Hall antisymmetrization than magnitude `R`.

For each matched gate point:

```text
R(+B) = X(+B) / Iac
R(-B) = X(-B) / Iac
Rxy_odd = (R(+B) - R(-B)) / 2
R_even = (R(+B) + R(-B)) / 2
n_2d = |B| / (e * Rxy_odd)
```

The sign of `n_2d` follows the sign of `Rxy_odd`.

## Guards

The analysis requires:

- both runs are completed `dual_gate_lockin_sweep` runs,
- both runs have `voltage_probe_role: hall`,
- both runs declare `magnetic_field_t`,
- the first run has positive field and the second has negative field,
- both fields have equal magnitude,
- both runs have the same gate grid.

