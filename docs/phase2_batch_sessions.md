# Phase 2 Batch Sessions

Batch sessions run several verified Drain I-V recipes in sequence. This is
useful for resistor smoke tests, repeated device checks, or comparing sweep
modes without manually launching each recipe.

## Batch YAML

Create a starter batch instead of writing YAML by hand:

```powershell
ptm new-batch configs/batches/my_repeat.yaml --kind repeat --name my_repeat --recipe configs/recipes/drain_iv_1k_resistor.yaml --repeat 3 --interval-s 1.0
ptm new-batch configs/batches/my_smoke_suite.yaml --kind smoke_suite --name my_smoke_suite
```

The command refuses to overwrite an existing file unless `--overwrite` is used.
After writing the YAML, it prints the same expanded plan used by `ptm batch`.

Example:

```yaml
name: drain_iv_1k_smoke_suite
stop_on_error: true
recipes:
  - label: linear
    recipe: ../recipes/drain_iv_1k_resistor.yaml
  - label: forward_backward
    recipe: ../recipes/drain_iv_1k_forward_backward.yaml
  - label: multi_segment
    recipe: ../recipes/drain_iv_1k_multisegment.yaml
```

Recipe paths are resolved relative to the batch YAML location first. Disabled
entries can be kept in the file with `enabled: false`.

Entries can repeat the same recipe:

```yaml
name: drain_iv_1k_repeat_linear
stop_on_error: true
checks:
  require_all_completed: true
  require_all_run_quality_pass: true
  max_relative_std_percent: 2.0
recipes:
  - label: linear_repeat
    recipe: ../recipes/drain_iv_1k_resistor.yaml
    repeat: 3
    interval_s: 0.5
```

This expands to labels `linear_repeat_rep01`, `linear_repeat_rep02`, and
`linear_repeat_rep03`. `interval_s` waits between repeated entries and is useful
for quick stability checks.

The optional `checks` block evaluates the whole batch after all runs finish:

- `require_all_completed`: every run must complete
- `require_all_run_quality_pass`: every run-level QC status must be `PASS`
- `max_relative_std_percent`: each repeated label group's fitted resistance
  relative standard deviation must be at or below this percent

## Dry-Run Batch

Use this before a real hardware session:

```powershell
ptm batch configs/batches/drain_iv_1k_smoke_suite.yaml --dry-run --fake-resistance-ohm 1000 --fake-noise-std-a 0 --summary --plot --report --batch-plot --batch-report --batch-csv --batch-points --batch-stats
```

Expected behavior:

- prints one combined `Batch plan`
- runs each enabled recipe with `FakeSMU`
- can simulate a specific resistor with `--fake-resistance-ohm` and
  `--fake-noise-std-a`
- writes normal per-run `points.csv`, `metadata.json`, `iv_plot.svg`, and
  `report.md`
- appends each run to `data/run_index.jsonl`
- writes `data/batches/<timestamp>_<batch_name>/batch_summary.json`
- writes `batch_overlay.svg` and `batch_report.md` when requested
- writes `batch_runs.csv` when requested
- writes `batch_points.csv` when requested
- writes `batch_stats.csv` when requested
- records per-run QC status when recipes define `checks`
- records batch-level QC status when the batch YAML defines `checks`

## Hardware Batch

Use this after checking the wiring, terminal selection, and safety preset:

```powershell
ptm batch configs/batches/drain_iv_1k_smoke_suite.yaml --summary --plot --report --batch-plot --batch-report --batch-csv --batch-points --batch-stats
```

Hardware batch behavior:

- prints the combined plan
- runs preflight for every enabled recipe before any sweep starts
- blocks the whole batch if any preflight fails
- asks once before enabling hardware output
- runs recipes sequentially
- turns output off and closes the instrument after each recipe through the
  existing Drain I-V runner

For deliberate unattended operation:

```powershell
ptm batch configs/batches/drain_iv_1k_smoke_suite.yaml --summary --plot --report --batch-plot --batch-report --batch-csv --batch-points --batch-stats --yes
```

## Reviewing A Saved Batch

Regenerate session-level review files from an existing batch folder:

```powershell
ptm batch-plot data\batches\<batch_folder>
ptm batch-report data\batches\<batch_folder>
ptm batch-csv data\batches\<batch_folder>
ptm batch-points data\batches\<batch_folder>
ptm batch-stats data\batches\<batch_folder>
```

Or point directly at the summary JSON:

```powershell
ptm batch-plot data\batches\<batch_folder>\batch_summary.json
ptm batch-report data\batches\<batch_folder>\batch_summary.json
ptm batch-csv data\batches\<batch_folder>\batch_summary.json
ptm batch-points data\batches\<batch_folder>\batch_summary.json
ptm batch-stats data\batches\<batch_folder>\batch_summary.json
```

Outputs:

- `batch_overlay.svg`: all plottable runs overlaid on one I-V plot
- `batch_report.md`: table of run status, points, fitted resistance, and paths
  including a QC status column
- `batch_runs.csv`: machine-readable table with repeat index, QC status, fitted
  resistance, voltage/current ranges, and output paths
- `batch_points.csv`: long-form table containing every measured point from all
  runs, with batch label and repeat columns for Origin/Excel/Python analysis
- `batch_stats.csv`: grouped repeat/stability table with mean fitted R, sample
  standard deviation, relative standard deviation, and QC pass/fail counts
- `batch_summary.json`: includes `quality.status` for batch-level PASS/FAIL

## Error Policy

By default, `stop_on_error: true` stops the batch after the first failed recipe.
Use `--continue-on-error` to keep running later recipes:

```powershell
ptm batch configs/batches/drain_iv_1k_smoke_suite.yaml --dry-run --continue-on-error
```

The batch summary records, for each recipe:

- label and recipe path
- completed/interrupted/error status
- points written
- run directory
- CSV, metadata, plot, and report paths

## Smoke-Test Checklist

```powershell
python -m pytest
ptm batch configs/batches/drain_iv_1k_smoke_suite.yaml --dry-run --fake-resistance-ohm 1000 --fake-noise-std-a 0 --summary --plot --report --batch-plot --batch-report --batch-csv --batch-points --batch-stats
ptm batch configs/batches/drain_iv_1k_repeat_linear.yaml --dry-run --fake-resistance-ohm 1000 --fake-noise-std-a 0 --summary --batch-csv --batch-points --batch-stats
ptm batch configs/batches/drain_iv_1k_smoke_suite.yaml --summary --plot --report --batch-plot --batch-report --batch-csv --batch-points --batch-stats
```

Expected 1 kOhm hardware result:

- all three recipes complete
- linear recipe has 21 points
- forward/backward recipe has 41 points
- multi-segment recipe has 21 points
- fitted resistance in each summary is near `1000 ohm`
- `batch_summary.json` has `completed: true`
- `batch_overlay.svg` and `batch_report.md` exist
- `batch_runs.csv` opens as a table with one row per run
- `batch_points.csv` opens as a table with all point rows from all runs
- `batch_stats.csv` opens as a table with one row per repeated label group
- `batch_summary.json` has `quality.status: PASS`

Quality check details are documented in `docs/phase3_quality_checks.md`.
