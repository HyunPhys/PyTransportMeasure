# Phase 10 Campaign Analytics Exports

Campaign analytics add quick resistance statistics and a histogram to a campaign
folder. This is meant for the common post-measurement question: "Which runs are
usable, and how tightly do the fitted resistances cluster?"

This phase reads saved files only and does not touch hardware.

## Create Analytics During Campaign Generation

```powershell
ptm campaign --name resistor_pass_only --sample resistor_box --device 1k_resistor --tag resistor --qc-status PASS --completed-only --min-resistance-ohm 900 --max-resistance-ohm 1100 --analytics
```

Additional files:

- `campaign_stats.csv`
- `campaign_resistance_histogram.svg`

`campaign_report.md` also includes a `Resistance Stats` section.

## Regenerate Analytics

From an existing campaign folder:

```powershell
ptm campaign-report data\campaigns\<campaign_folder>
ptm campaign-stats data\campaigns\<campaign_folder>
ptm campaign-histogram data\campaigns\<campaign_folder>
```

Or point directly at the manifest:

```powershell
ptm campaign-stats data\campaigns\<campaign_folder>\campaign_manifest.json
ptm campaign-histogram data\campaigns\<campaign_folder>\campaign_manifest.json --bins 16
```

## Stats Grouping

`campaign_stats.csv` groups raw runs by:

- `sample_id`
- `device_id`
- `measurement_name`
- `quality_status`

For each group it records:

- run count
- completed count
- QC PASS/FAIL counts
- mean fitted resistance
- sample standard deviation
- relative standard deviation
- min/max fitted resistance
- mean point count

## Smoke-Test Checklist

```powershell
python -m pytest
ptm campaign --name resistor_analytics_check --sample resistor_box --device 1k_resistor --tag resistor --qc-status PASS --completed-only --min-resistance-ohm 900 --max-resistance-ohm 1100 --analytics
ptm campaign-stats data\campaigns\<campaign_folder>
ptm campaign-histogram data\campaigns\<campaign_folder>
```

Expected result:

- `campaign_stats.csv` exists and contains grouped resistance statistics
- `campaign_resistance_histogram.svg` opens and shows the fitted resistance distribution
- `campaign_report.md` includes `Resistance Stats`
- commands do not communicate with the Keithley
