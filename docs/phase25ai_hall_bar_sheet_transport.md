# Phase 25ai: Hall-Bar Sheet Transport

This phase adds optional Hall-bar channel geometry to dual-gate lock-in
topology and derives sheet transport values for longitudinal voltage probes.

## Scope

`topology` now supports:

- `voltage_probe_role`: `longitudinal`, `hall`, or `generic`
- `channel_length_m`
- `channel_width_m`

For `voltage_probe_role: longitudinal`, both length and width must be supplied
together. The runner computes:

```text
lockin_sheet_resistance_ohm_per_sq = lockin_resistance_ohm * channel_width_m / channel_length_m
lockin_sheet_conductivity_s_per_sq = 1 / lockin_sheet_resistance_ohm_per_sq
```

For `voltage_probe_role: hall`, length/width are rejected for now. Hall
coefficient, carrier density, and mobility extraction are left for a later
phase where magnetic-field metadata is introduced.

## Artifacts

The new values are written to:

- `points.csv`
- `dual_gate_lockin_stats.csv`
- CLI summary
- `dual_gate_lockin_report.md`

Older runs without these columns still load; the review layer treats missing
sheet transport values as `None`.

## Lab Checklist

- Confirm `voltage_probe_role` matches the actual voltage contact pair.
- For Vxx, enter voltage-probe spacing as `channel_length_m`.
- Enter Hall-bar width as `channel_width_m`.
- Confirm generated reports show sheet resistance only for longitudinal Vxx
  recipes with both geometry values declared.
