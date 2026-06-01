# Phase 15 Single-Gate Scheme Steps

Single-gate recipes can now be part of a measurement scheme alongside Drain I-V
recipes and batch steps. This is a step toward user-composable measurement
workflows where a YAML scheme describes the whole session.

## Example Scheme

```powershell
configs\schemes\single_gate_dry_run_scheme.yaml
```

It combines:

```yaml
steps:
  - type: drain_iv
    label: drain_reference
    recipe: ../recipes/drain_iv_1k_resistor.yaml
  - type: single_gate
    label: gate_transfer_map
    recipe: ../recipes/single_gate_dry_run.yaml
```

Single-gate scheme steps currently use the recipe as-is. Overrides and matrix
expansion remain limited to Drain I-V steps until the two-SMU workflow has had
hardware smoke testing.

## Commands

Preview:

```powershell
ptm scheme-plan configs\schemes\single_gate_dry_run_scheme.yaml
```

Dry-run:

```powershell
ptm scheme configs\schemes\single_gate_dry_run_scheme.yaml --dry-run --fake-resistance-ohm 1000 --fake-channel-resistance-ohm 1000000 --fake-noise-std-a 0 --summary --plot --report --gate-stats --scheme-runs --scheme-points --scheme-stats
```

## Output Behavior

- Drain I-V steps still write normal `points.csv`, optional `iv_plot.svg`, and
  `report.md`.
- Single-gate steps write normal `points.csv` plus optional
  `single_gate_heatmap.svg`, `single_gate_stats.csv`, and
  `single_gate_report.md`.
- `scheme_summary.json` stores both step types.
- `scheme_runs.csv` includes gate-specific summary columns when present.
- `scheme_points.csv` includes both Drain I-V columns and single-gate columns.
- `scheme_overlay.svg` overlays only Drain I-V style traces and skips
  single-gate heatmaps.

## Smoke-Test Checklist

```powershell
python -m pytest
ptm scheme-plan configs\schemes\single_gate_dry_run_scheme.yaml
ptm scheme configs\schemes\single_gate_dry_run_scheme.yaml --dry-run --fake-resistance-ohm 1000 --fake-channel-resistance-ohm 1000000 --fake-noise-std-a 0 --summary --plot --report --gate-stats --scheme-runs --scheme-points --scheme-stats
```

Expected result:

- plan shows one `drain_iv` step and one `single_gate` step
- scheme completes successfully
- `scheme_summary.json` contains both step types
- the single-gate run folder contains `single_gate_heatmap.svg`,
  `single_gate_stats.csv`, and `single_gate_report.md`
- `scheme_runs.csv` includes `gate_points`
- `scheme_points.csv` includes `gate_voltage_v`
