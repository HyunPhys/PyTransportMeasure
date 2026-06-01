# Phase 13 Single-Gate Review Exports

Single-gate review exports make saved gate/drain sweeps easier to inspect before
moving to real two-SMU hardware validation.

This phase reads saved files only, except when `ptm single-gate` is actively
running a measurement.

## During A Run

```powershell
ptm single-gate configs\recipes\single_gate_dry_run.yaml --dry-run --summary --plot --report --gate-stats --fake-channel-resistance-ohm 1000000 --fake-noise-std-a 0
```

Optional exports:

- `--summary`: print a single-gate summary
- `--plot`: write `single_gate_heatmap.svg`
- `--report`: write `single_gate_report.md`
- `--gate-stats`: write `single_gate_stats.csv`

## From A Saved Run

```powershell
ptm single-gate-summary data\raw\<run_folder>
ptm single-gate-plot data\raw\<run_folder>
ptm single-gate-stats data\raw\<run_folder>
ptm single-gate-report data\raw\<run_folder>
```

## Output Files

```text
single_gate_heatmap.svg
single_gate_stats.csv
single_gate_report.md
```

`single_gate_stats.csv` contains one row per gate voltage:

- gate voltage
- point count
- drain current min/max
- gate current mean
- maximum absolute gate leakage
- fitted drain resistance for that gate slice

The heatmap shows drain current as a function of drain voltage and gate voltage.

## Smoke-Test Checklist

```powershell
python -m pytest
ptm single-gate configs\recipes\single_gate_dry_run.yaml --dry-run --summary --plot --report --gate-stats --fake-channel-resistance-ohm 1000000 --fake-noise-std-a 0
ptm single-gate-summary data\raw\<run_folder>
ptm single-gate-plot data\raw\<run_folder>
ptm single-gate-stats data\raw\<run_folder>
ptm single-gate-report data\raw\<run_folder>
```

Expected result:

- `Metadata completed: True`
- summary shows `Points: 55`, `Gate points: 5`, and `Drain points per gate: 11`
- `single_gate_heatmap.svg` exists and opens
- `single_gate_stats.csv` has 5 data rows
- `single_gate_report.md` includes `Gate Statistics` and links the heatmap
- dry-run does not communicate with VISA or Keithley hardware
