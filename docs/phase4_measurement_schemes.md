# Phase 4 Measurement Schemes

Measurement schemes are the first layer above single recipes and batch sessions.
They let one YAML file describe a larger measurement workflow made of Drain I-V
steps and nested batch steps.

This is still deliberately conservative: scheme v0 does not add variables,
conditionals, GUI editing, SR860, gate sweeps, or pulse timing. It only composes
already verified Drain I-V and batch machinery so the hardware behavior remains
traceable.

For recipe-step parameter overrides, see `docs/phase5_scheme_overrides.md`.

## Scheme YAML

Create a starter scheme:

```powershell
ptm new-scheme configs/schemes/my_scheme.yaml --kind recipe_and_batch --name my_scheme --recipe configs/recipes/drain_iv_1k_resistor.yaml --batch configs/batches/drain_iv_1k_repeat_linear.yaml
ptm new-scheme configs/schemes/my_repeat_scheme.yaml --kind repeat_recipe --name my_repeat_scheme --recipe configs/recipes/drain_iv_1k_resistor.yaml --repeat 3 --interval-s 1.0
```

The command refuses to overwrite an existing file unless `--overwrite` is used.
After writing the YAML, it prints the expanded scheme plan.

Example:

```yaml
name: drain_iv_1k_recipe_and_batch
stop_on_error: true
steps:
  - type: drain_iv
    label: linear_once
    recipe: ../recipes/drain_iv_1k_resistor.yaml
  - type: batch
    label: repeat_stability
    batch: ../batches/drain_iv_1k_repeat_linear.yaml
```

Step paths are resolved relative to the scheme YAML location first. A step can
be disabled with `enabled: false`.

Recipe steps can repeat:

```yaml
name: repeated_contact_check
stop_on_error: true
steps:
  - type: drain_iv
    label: contact_check
    recipe: ../recipes/drain_iv_1k_resistor.yaml
    repeat: 3
    interval_s: 0.5
```

This expands to labels `contact_check_rep01`, `contact_check_rep02`, and
`contact_check_rep03`.

## Plan And Dry Run

Inspect the full scheme without touching hardware:

```powershell
ptm scheme-plan configs/schemes/drain_iv_1k_recipe_and_batch.yaml
```

Run the same workflow with `FakeSMU`:

```powershell
ptm scheme configs/schemes/drain_iv_1k_recipe_and_batch.yaml --dry-run --fake-resistance-ohm 1000 --fake-noise-std-a 0 --summary --plot --report --batch-csv --batch-points --batch-stats --batch-report
```

Expected behavior:

- prints one combined `Scheme plan`
- runs direct Drain I-V steps and nested batch steps sequentially
- writes normal per-run `points.csv`, `metadata.json`, optional `iv_plot.svg`,
  and optional `report.md`
- writes nested batch summaries under the scheme folder
- writes `scheme_summary.json`, `scheme_report.md`, and `scheme_steps.csv`
- records whether each step completed
- stops after a failed step when `stop_on_error: true`

## Hardware Scheme

Use this only after checking the wiring, terminal selection, and safety preset:

```powershell
ptm scheme configs/schemes/drain_iv_1k_recipe_and_batch.yaml --summary --plot --report --batch-csv --batch-points --batch-stats --batch-report
```

Hardware scheme behavior:

- prints the combined scheme plan
- runs preflight for every direct recipe and every recipe inside nested batches
  before any sweep starts
- blocks the whole scheme if any preflight fails
- asks once before enabling hardware output
- runs steps sequentially
- turns output off and closes the Keithley after each individual Drain I-V run

For deliberate unattended operation:

```powershell
ptm scheme configs/schemes/drain_iv_1k_recipe_and_batch.yaml --summary --plot --report --batch-csv --batch-points --batch-stats --batch-report --yes
```

## Outputs

Each scheme folder is written under `data/schemes` by default:

- `scheme_summary.json`: machine-readable status and output paths for each step
- `scheme_report.md`: human-readable table of step status
- `scheme_steps.csv`: one row per expanded scheme step
- `batches/<timestamp>_<batch_name>/batch_summary.json`: nested batch summary
  files for batch steps

Every Drain I-V measurement still writes its normal run folder under
`data/raw`, so existing commands keep working:

```powershell
ptm inspect-run data\raw\<run_folder>
ptm check-run data\raw\<run_folder>
ptm report data\raw\<run_folder>
ptm summarize data\raw\<run_folder>
```

## Smoke-Test Checklist

```powershell
python -m pytest
ptm scheme-plan configs/schemes/drain_iv_1k_recipe_and_batch.yaml
ptm scheme configs/schemes/drain_iv_1k_recipe_and_batch.yaml --dry-run --fake-resistance-ohm 1000 --fake-noise-std-a 0 --summary --plot --report --batch-csv --batch-points --batch-stats --batch-report
ptm scheme configs/schemes/drain_iv_1k_recipe_and_batch.yaml --summary --plot --report --batch-csv --batch-points --batch-stats --batch-report
```

Expected 1 kOhm hardware result:

- direct `linear_once` step completes
- nested `repeat_stability` batch completes
- every run-level quality status is `PASS`
- nested batch quality status is `PASS`
- `scheme_summary.json` has `completed: true`
- `scheme_report.md` and `scheme_steps.csv` exist
- fitted resistance values remain near `1000 ohm`
