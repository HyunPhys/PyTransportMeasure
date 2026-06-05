# Phase 25aj: Hall-Voltage Transport

This phase adds Vxy-specific derived transport to the dual-gate lock-in path.

## Scope

`topology` now supports optional:

```yaml
voltage_probe_role: hall
magnetic_field_t: 1.0
```

For `voltage_probe_role: hall`, the generic lock-in resistance is also saved as:

```text
lockin_hall_resistance_ohm
```

If `magnetic_field_t` is available and Hall resistance is nonzero, the runner
also estimates:

```text
lockin_hall_carrier_density_per_m2 = magnetic_field_t / (e * lockin_hall_resistance_ohm)
```

The sign is preserved. This is intentionally a first-pass fixed-field estimate,
not a full antisymmetrized Hall analysis.

## New Recipe

- `configs/recipes/dual_gate_lockin_hall_dry_run.yaml`

## Artifacts

The Hall values are written to:

- `points.csv`
- `dual_gate_lockin_stats.csv`
- CLI summary
- `dual_gate_lockin_report.md`

## Lab Checklist

- Confirm `magnetic_field_t` sign matches the lab convention.
- Confirm Vxy contacts are transverse Hall contacts, not longitudinal contacts.
- Treat carrier density as provisional until B-sweep or +/-B antisymmetrization
  is implemented.
