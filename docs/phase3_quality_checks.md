# Phase 3 Quality Checks

Quality checks turn smoke-test measurements into explicit PASS/FAIL results.
They are stored in the recipe and evaluated after each run.

## Recipe Checks

Example for a 1 kOhm resistor:

```yaml
checks:
  require_completed: true
  min_points: 21
  fitted_resistance_ohm:
    min_ohm: 900
    max_ohm: 1100
```

Supported checks:

- `require_completed`: run must finish without runner error
- `min_points`: saved `points.csv` must contain at least this many points
- `fitted_resistance_ohm.min_ohm` / `max_ohm`: fitted resistance window

The `ptm plan` output includes the configured checks before hardware access.

## During A Run

After points are saved, `ptm run` evaluates checks and writes the result into
`metadata.json`:

```json
{
  "quality": {
    "status": "PASS",
    "results": [
      {
        "name": "fitted_resistance_ohm",
        "passed": true,
        "message": "fitted=1000 ohm, min=900 ohm, max=1100 ohm"
      }
    ]
  }
}
```

The generated `report.md` includes a `Quality` section.

## Rechecking A Saved Run

```powershell
ptm check-run data\raw\<run_folder>
```

Exit code behavior:

- `PASS`: exit code `0`
- `SKIP`: exit code `0`, used when recipe has no `checks` block
- `FAIL`: exit code `2`

## Batch Reports

Batch summaries store each run's quality result. `batch_report.md` includes a
QC column:

```powershell
ptm batch configs/batches/drain_iv_1k_smoke_suite.yaml --summary --plot --report --batch-plot --batch-report
```

For the 1 kOhm smoke suite, hardware runs should report `PASS` for all three
recipes.

Dry-run defaults use a fake 10 MOhm source, so 1 kOhm recipes report `FAIL`.
Use a 1 kOhm fake source when you want dry-run to exercise the full PASS path:

```powershell
ptm run configs/recipes/drain_iv_1k_resistor.yaml --dry-run --fake-resistance-ohm 1000 --fake-noise-std-a 0 --summary --report
ptm batch configs/batches/drain_iv_1k_smoke_suite.yaml --dry-run --fake-resistance-ohm 1000 --fake-noise-std-a 0 --summary --batch-report
```

The fake resistance and noise settings are saved in `metadata.json` under
`instrument_probe`.

Batch YAML files can also define session-level checks:

```yaml
checks:
  require_all_completed: true
  require_all_run_quality_pass: true
  max_relative_std_percent: 2.0
```

These checks write `quality.status` into `batch_summary.json` and add a `Batch
Quality` section to `batch_report.md`.
