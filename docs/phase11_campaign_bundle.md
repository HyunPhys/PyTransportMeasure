# Phase 11 Campaign Bundle Export

Campaign bundles create a portable folder and ZIP archive from a saved campaign.
Use this when you want to back up a curated analysis set, move it to another
computer, or attach a compact package to a lab note.

This phase reads saved files only and does not touch hardware.

## Create A Bundle

From a campaign folder:

```powershell
ptm campaign-bundle data\campaigns\<campaign_folder>
```

Or from a manifest path:

```powershell
ptm campaign-bundle data\campaigns\<campaign_folder>\campaign_manifest.json
```

Default output root:

```text
data/exports
```

The command creates:

```text
data/exports/<timestamp>_<campaign_name>_bundle/
data/exports/<timestamp>_<campaign_name>_bundle.zip
```

## Bundle Contents

The bundle folder contains:

```text
campaign/
  campaign_manifest.json
  campaign_runs.csv
  campaign_stats.csv
  campaign_report.md
  campaign_resistance_histogram.svg
runs/
  001_<run_name>/
    metadata.json
    points.csv
    recipe_snapshot.yaml
    safety_snapshot.yaml
    iv_plot.svg
    report.md
summaries/
  batches/
  schemes/
bundle_manifest.json
```

Only files that exist are copied.

## Smaller Bundles

Skip large point tables, plots, or reports:

```powershell
ptm campaign-bundle data\campaigns\<campaign_folder> --no-points
ptm campaign-bundle data\campaigns\<campaign_folder> --no-plots
ptm campaign-bundle data\campaigns\<campaign_folder> --no-reports
```

Options can be combined:

```powershell
ptm campaign-bundle data\campaigns\<campaign_folder> --no-points --no-plots
```

## Smoke-Test Checklist

```powershell
python -m pytest
ptm campaign --name bundle_check --sample resistor_box --device 1k_resistor --tag resistor --qc-status PASS --completed-only --min-resistance-ohm 900 --max-resistance-ohm 1100 --analytics
ptm campaign-bundle data\campaigns\<campaign_folder>
```

Expected result:

- bundle folder exists under `data/exports`
- ZIP file exists next to the bundle folder
- `bundle_manifest.json` exists
- `campaign/campaign_manifest.json` exists
- `runs/*/metadata.json` exists
- `runs/*/recipe_snapshot.yaml` and `runs/*/safety_snapshot.yaml` are included when available
- command does not communicate with the Keithley
