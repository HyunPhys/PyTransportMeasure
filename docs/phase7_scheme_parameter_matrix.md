# Phase 7 Scheme Parameter Matrix

Scheme matrix rows let one Drain I-V step expand into several measurement
conditions. This keeps a sweep series readable as a table instead of forcing a
separate YAML step for every bias range.

## Example

```yaml
name: drain_iv_1k_bias_matrix
stop_on_error: true
steps:
  - type: drain_iv
    label: bias
    recipe: ../recipes/drain_iv_1k_resistor.yaml
    overrides:
      experiment:
        append_tags:
          - scheme
          - matrix
    matrix:
      rows:
        - label: low
          overrides:
            measurement_suffix: _matrix_low
            experiment:
              append_tags:
                - low-bias
            sweep:
              start_v: -0.05
              stop_v: 0.05
              points: 11
              delay_s: 0.02
        - label: nominal
          overrides:
            measurement_suffix: _matrix_nominal
            experiment:
              append_tags:
                - nominal-bias
            sweep:
              start_v: -0.1
              stop_v: 0.1
              points: 21
              delay_s: 0.05
```

The step-level `overrides` are applied first. Each matrix row's `overrides` are
then applied on top. `experiment.append_tags` from the step and the row are
combined, so a row can inherit common tags and add its own condition tag.

The example expands into labels:

- `bias_low`
- `bias_mid`
- `bias_nominal`

If `repeat: 2` is also set, labels become `bias_low_rep01`,
`bias_low_rep02`, `bias_mid_rep01`, and so on.

## Commands

Preview:

```powershell
ptm scheme-plan configs/schemes/drain_iv_1k_bias_matrix.yaml
```

Dry-run:

```powershell
ptm scheme configs/schemes/drain_iv_1k_bias_matrix.yaml --dry-run --fake-resistance-ohm 1000 --fake-noise-std-a 0 --summary --plot --report --scheme-plot --scheme-runs --scheme-points --scheme-stats
```

Hardware run with a 1 kOhm resistor:

```powershell
ptm scheme configs/schemes/drain_iv_1k_bias_matrix.yaml --summary --plot --report --scheme-plot --scheme-runs --scheme-points --scheme-stats
```

## Output Metadata

Each expanded step records matrix context in `scheme_summary.json` and
`scheme_steps.csv`:

- `matrix_label`
- `matrix_index`
- `matrix_count`

Each run still writes a normal `recipe_snapshot.yaml` containing the actual
row-specific recipe.

## Smoke-Test Checklist

```powershell
python -m pytest
ptm scheme-plan configs/schemes/drain_iv_1k_bias_matrix.yaml
ptm scheme configs/schemes/drain_iv_1k_bias_matrix.yaml --dry-run --fake-resistance-ohm 1000 --fake-noise-std-a 0 --summary --plot --report --scheme-plot --scheme-runs --scheme-points --scheme-stats
ptm scheme configs/schemes/drain_iv_1k_bias_matrix.yaml --summary --plot --report --scheme-plot --scheme-runs --scheme-points --scheme-stats
```

Expected 1 kOhm hardware result:

- `bias_low` completes with 11 points from `-0.05 V` to `0.05 V`
- `bias_mid` completes with 15 points from `-0.075 V` to `0.075 V`
- `bias_nominal` completes with 21 points from `-0.1 V` to `0.1 V`
- every run has QC `PASS`
- `scheme_summary.json` has `completed: true` and `quality.status: PASS`
- `scheme_overlay.svg`, `scheme_runs.csv`, `scheme_points.csv`, and
  `scheme_stats.csv` are created
