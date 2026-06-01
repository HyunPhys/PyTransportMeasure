# Phase 9 Campaign Curation

Campaign curation filters saved raw runs before creating the campaign manifest.
This is for the point where the data folder is no longer small: you can create
one campaign for all runs, and another campaign containing only the runs that
belong to a specific sample, device, tag, QC status, or fitted resistance range.

This command still does not touch hardware.

## Filter Examples

Only completed 1 kOhm resistor runs with PASS QC:

```powershell
ptm campaign --name resistor_pass_only --sample resistor_box --device 1k_resistor --tag resistor --qc-status PASS --completed-only
```

Only runs whose fitted resistance is near 1 kOhm:

```powershell
ptm campaign --name resistor_1k_window --min-resistance-ohm 900 --max-resistance-ohm 1100
```

Only failed or interrupted runs:

```powershell
ptm campaign --name failed_runs --failed-only
ptm campaign --name incomplete_runs --incomplete-only
```

Only runs with a measurement name fragment:

```powershell
ptm campaign --name matrix_runs --measurement-contains matrix
```

## Available Filters

- `--sample`
- `--device`
- `--tag`
- `--qc-status PASS|FAIL|SKIP|n/a`
- `--completed-only`
- `--incomplete-only`
- `--failed-only`
- `--measurement-contains`
- `--min-resistance-ohm`
- `--max-resistance-ohm`

Filters apply to raw run entries. Batch and scheme tables are still included as
session context. The output manifest records both filtered `counts` and
`source_counts`, so it is clear how many source runs were scanned before
filtering.

## Outputs

The same campaign files are written:

- `campaign_manifest.json`
- `campaign_runs.csv`
- `campaign_report.md`

`campaign_report.md` includes a `Filters` section whenever filters are active.

## Smoke-Test Checklist

```powershell
python -m pytest
ptm campaign --name resistor_pass_only --sample resistor_box --device 1k_resistor --tag resistor --qc-status PASS --completed-only --min-resistance-ohm 900 --max-resistance-ohm 1100
```

Expected result:

- `campaign_manifest.json` includes `filters`
- `source_counts.runs` is greater than or equal to `counts.runs`
- `campaign_runs.csv` only contains runs matching the filter
- `campaign_report.md` includes a `Filters` section
