# Phase 14 Mixed Run Support

Mixed run support lets Drain I-V and single-gate runs live together under
`data/raw` without breaking inspection, indexing, campaigns, or bundle exports.

## What Changed

- Run index records now include `measurement_type`.
- `ptm list-runs` can filter by measurement type.
- `ptm inspect-run` recognizes `single_gate_sweep` metadata and prints the
  single-gate summary instead of trying to parse the file as a Drain I-V run.
- Campaign manifests collect single-gate summaries:
  - gate point count
  - drain point count
  - gate voltage range
  - drain voltage/current range
  - maximum absolute gate leakage
- Campaign reports include run type and gate-specific columns in the recent run
  table.
- Campaign bundles include single-gate review artifacts when present.
- `ptm campaign --analytics` still writes stats for single-gate-only campaigns
  and skips the resistance histogram when no fitted Drain I-V resistance values
  exist.

## Commands

```powershell
ptm rebuild-index
ptm list-runs --measurement-type single_gate_sweep
ptm inspect-run data\raw\<single_gate_run_folder>
ptm campaign --name mixed_runs_check
ptm campaign-bundle data\campaigns\<campaign_folder>
```

## Smoke-Test Checklist

Create a dry-run single-gate run:

```powershell
ptm single-gate configs\recipes\single_gate_dry_run.yaml --dry-run --summary --plot --report --gate-stats --fake-channel-resistance-ohm 1000000 --fake-noise-std-a 0
```

Then verify:

```powershell
ptm inspect-run data\raw\<single_gate_run_folder>
ptm rebuild-index
ptm list-runs --measurement-type single_gate_sweep
ptm campaign --name mixed_single_gate_check --measurement-contains single_gate
ptm campaign-bundle data\campaigns\<campaign_folder>
```

Expected result:

- inspect output shows `Measurement type: single_gate_sweep`
- inspect output shows gate points and drain points per gate
- list-runs output shows `type=single_gate_sweep`
- campaign manifest contains the single-gate run without `summary_error`
- campaign report recent run table includes run type and gate leakage columns
- campaign bundle includes `single_gate_heatmap.svg`,
  `single_gate_stats.csv`, and `single_gate_report.md` when those files exist
