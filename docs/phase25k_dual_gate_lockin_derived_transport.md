# Phase 25k: Dual-Gate Lock-In Derived Transport

This phase adds source-drain transport analysis columns to dual-gate lock-in
runs.

## Scope

- Add point CSV columns:
  - `source_drain_excitation_v`
  - `source_drain_nominal_current_a`
  - `lockin_resistance_ohm`
  - `lockin_conductance_s`
- Save nominal excitation metadata in `metadata.json`.
- Add per-gate-pair resistance and conductance statistics.
- Add resistance and conductance ranges to summaries and reports.
- Keep older saved dual-gate lock-in runs readable by treating the new columns
  as optional during review.

## Transport Model

For Hall-bar-style SR860 excitation through a current-bias resistor, the nominal
source-drain AC current is estimated as:

```text
source_drain_nominal_current_a = excitation_amplitude_v / current_bias_resistor_ohm
```

The reported lock-in resistance is:

```text
lockin_resistance_ohm = lockin_r_v / source_drain_nominal_current_a
```

The reported conductance is:

```text
lockin_conductance_s = 1 / lockin_resistance_ohm
```

These are analysis values derived from recipe topology and measured lock-in R.
They do not change SR860 or Keithley hardware configuration.

## Lab Checklist

```powershell
ptm dual-gate-lockin configs/recipes/dual_gate_lockin_dry_run.yaml --dry-run --summary --plot --report --gate-stats --fake-noise-std 0
```

- Confirm `points.csv` includes the new source-drain transport columns.
- Confirm `metadata.json` records `source_drain_nominal_current_a`.
- Confirm `dual_gate_lockin_stats.csv` includes resistance and conductance
  statistics.
- Confirm `dual_gate_lockin_report.md` lists nominal current, resistance range,
  and conductance range.
