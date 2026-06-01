# Phase 5 Scheme Overrides

Scheme overrides let one verified base recipe generate several measurement
variants without copying YAML files. This is the first step toward a practical
recipe builder: the stable base recipe keeps instrument identity, safety preset,
metadata, and quality checks, while each scheme step can override only the
fields that change.

## Example

```yaml
name: drain_iv_1k_bias_series
stop_on_error: true
steps:
  - type: drain_iv
    label: low_bias
    recipe: ../recipes/drain_iv_1k_resistor.yaml
    overrides:
      measurement_suffix: _low_bias
      experiment:
        append_tags:
          - scheme
          - low-bias
      sweep:
        start_v: -0.05
        stop_v: 0.05
        points: 11
        delay_s: 0.02
  - type: drain_iv
    label: nominal_bias
    recipe: ../recipes/drain_iv_1k_resistor.yaml
    overrides:
      measurement_suffix: _nominal_bias
      experiment:
        append_tags:
          - scheme
          - nominal-bias
      sweep:
        start_v: -0.1
        stop_v: 0.1
        points: 21
        delay_s: 0.05
```

Run:

```powershell
ptm scheme-plan configs/schemes/drain_iv_1k_bias_series.yaml
ptm scheme configs/schemes/drain_iv_1k_bias_series.yaml --dry-run --fake-resistance-ohm 1000 --fake-noise-std-a 0 --summary --plot --report
```

## Supported Override Fields

Top-level:

- `measurement_name`: replace the measurement name completely
- `measurement_suffix`: append a suffix to the base measurement name
- `safety_preset`: use a different named safety preset

Nested fields:

- `experiment.sample_id`
- `experiment.device_id`
- `experiment.operator`
- `experiment.notes`
- `experiment.tags`
- `experiment.append_tags`
- `instrument.address`
- `instrument.timeout_ms`
- `instrument.terminal`
- `instrument.voltage_range_v`
- `instrument.current_range_a`
- `sweep.mode`
- `sweep.start_v`
- `sweep.stop_v`
- `sweep.points`
- `sweep.delay_s`
- `sweep.current_compliance_a`
- `sweep.segments`
- `output.directory`
- `checks`

`experiment.tags` replaces the tag list. `experiment.append_tags` preserves the
base tags and appends only new tags.

## Safety Behavior

Overrides are applied before plan, preflight, and run:

- `ptm scheme-plan` previews the actual overridden sweep
- hardware `ptm scheme` validates the overridden recipe before output is enabled
- hardware `ptm scheme` probes the overridden instrument address
- the run folder `recipe_snapshot.yaml` stores the actual applied recipe
- the base recipe file is not modified

If an override makes the sweep exceed the selected safety preset, the command
fails before measurement.

## Smoke-Test Checklist

```powershell
python -m pytest
ptm scheme-plan configs/schemes/drain_iv_1k_bias_series.yaml
ptm scheme configs/schemes/drain_iv_1k_bias_series.yaml --dry-run --fake-resistance-ohm 1000 --fake-noise-std-a 0 --summary --plot --report
ptm scheme configs/schemes/drain_iv_1k_bias_series.yaml --summary --plot --report
```

Expected 1 kOhm hardware result:

- `low_bias` creates a run folder ending in `_low_bias`
- `low_bias` has 11 points from `-0.05 V` to `0.05 V`
- `nominal_bias` creates a run folder ending in `_nominal_bias`
- `nominal_bias` has 21 points from `-0.1 V` to `0.1 V`
- both runs have QC `PASS`
- `scheme_summary.json` has `completed: true`
- each run's `recipe_snapshot.yaml` contains the overridden sweep
