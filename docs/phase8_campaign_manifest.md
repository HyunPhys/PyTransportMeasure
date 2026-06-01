# Phase 8 Campaign Manifest

Campaign manifests collect saved runs, batches, and schemes into one experiment
log folder. This is useful after a day of measurements: instead of opening many
run folders by hand, create one campaign folder containing a JSON manifest, a
run table CSV, and a Markdown report.

This phase does not touch hardware. It only scans saved data.

## Command

```powershell
ptm campaign --name resistor_day1
```

Default scan roots:

- `data/raw`
- `data/batches`
- `data/schemes`

Default output root:

- `data/campaigns`

Full form:

```powershell
ptm campaign --name resistor_day1 --raw-dir data/raw --batch-dir data/batches --scheme-dir data/schemes --output-dir data/campaigns
```

## Outputs

The command creates:

```text
data/campaigns/<timestamp>_<name>/
  campaign_manifest.json
  campaign_runs.csv
  campaign_report.md
```

`campaign_manifest.json` contains:

- generation time
- scanned roots
- run counts
- batch counts
- scheme counts
- one entry per raw run
- one entry per batch summary
- one entry per scheme summary

`campaign_runs.csv` contains one row per raw run with:

- measurement name
- timestamps
- completion and QC status
- sample/device/operator/tags
- points and fitted resistance
- voltage/current ranges
- error state
- run directory
- recipe path

`campaign_report.md` contains:

- high-level completion counts
- run QC counts
- recent run table
- batch table
- scheme table

## Smoke-Test Checklist

```powershell
python -m pytest
ptm campaign --name resistor_campaign_check
```

Expected result:

- `data/campaigns/<timestamp>_resistor_campaign_check` exists
- `campaign_manifest.json` exists and has `counts`
- `campaign_runs.csv` opens as a table
- `campaign_report.md` opens and lists runs, batches, and schemes
- command does not communicate with the Keithley
