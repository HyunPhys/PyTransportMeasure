# Phase 6 Scheme Review Exports

Scheme review exports turn a completed scheme folder into files that are easier
to inspect and analyze after a measurement session. The exports flatten direct
Drain I-V steps and nested batch runs into one scheme-level view.

## During A Scheme Run

Add scheme-level export flags:

```powershell
ptm scheme configs/schemes/drain_iv_1k_bias_series.yaml --dry-run --fake-resistance-ohm 1000 --fake-noise-std-a 0 --summary --plot --report --scheme-plot --scheme-runs --scheme-points --scheme-stats
```

For a real 1 kOhm check:

```powershell
ptm scheme configs/schemes/drain_iv_1k_bias_series.yaml --summary --plot --report --scheme-plot --scheme-runs --scheme-points --scheme-stats
```

Every scheme run always writes:

- `scheme_summary.json`
- `scheme_report.md`
- `scheme_steps.csv`

The extra flags write:

- `scheme_overlay.svg`: all plottable runs overlaid in one I-V plot
- `scheme_runs.csv`: one row per actual Drain I-V run
- `scheme_points.csv`: one long-form table with every point from every run
- `scheme_stats.csv`: grouped statistics by scheme step

## After A Scheme Run

Regenerate exports from an existing scheme folder:

```powershell
ptm scheme-report data\schemes\<scheme_folder>
ptm scheme-plot data\schemes\<scheme_folder>
ptm scheme-runs data\schemes\<scheme_folder>
ptm scheme-points data\schemes\<scheme_folder>
ptm scheme-stats data\schemes\<scheme_folder>
```

Or point directly at the summary JSON:

```powershell
ptm scheme-report data\schemes\<scheme_folder>\scheme_summary.json
ptm scheme-plot data\schemes\<scheme_folder>\scheme_summary.json
ptm scheme-runs data\schemes\<scheme_folder>\scheme_summary.json
ptm scheme-points data\schemes\<scheme_folder>\scheme_summary.json
ptm scheme-stats data\schemes\<scheme_folder>\scheme_summary.json
```

## Quality Rollup

`scheme_summary.json` now gets a `quality` block:

- `all_completed`: every actual run in the scheme completed
- `no_run_quality_failures`: no direct or nested run has QC `FAIL`

Nested batch runs are included in the flattened scheme review. If a scheme
contains one direct recipe and one nested batch with three repeats, the scheme
review sees four actual runs.

## Smoke-Test Checklist

```powershell
python -m pytest
ptm scheme configs/schemes/drain_iv_1k_bias_series.yaml --dry-run --fake-resistance-ohm 1000 --fake-noise-std-a 0 --summary --plot --report --scheme-plot --scheme-runs --scheme-points --scheme-stats
ptm scheme-report data\schemes\<scheme_folder>
ptm scheme-plot data\schemes\<scheme_folder>
ptm scheme-runs data\schemes\<scheme_folder>
ptm scheme-points data\schemes\<scheme_folder>
ptm scheme-stats data\schemes\<scheme_folder>
```

Expected result:

- `scheme_summary.json` has `quality.status: PASS`
- `scheme_report.md` includes `Scheme QC: PASS`
- `scheme_overlay.svg` opens and shows both I-V curves
- `scheme_runs.csv` has one row per run
- `scheme_points.csv` has all measured points
- `scheme_stats.csv` has grouped resistance statistics
