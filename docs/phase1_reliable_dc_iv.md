# Phase 1 Reliable DC I-V

Phase 1 turns the verified Phase 0 smoke test into a more comfortable daily DC
I-V tool.

## Implemented First

- `ptm run <recipe> --summary` prints the same summary as `ptm summarize`.
- `ptm run <recipe> --plot` writes `iv_plot.svg` after a run with data points.
- `ptm run <recipe> --report` writes `report.md` after measurement.
- `ptm report <run_dir>` writes or rewrites a Markdown report for a saved run.
- `ptm run <recipe> --progress` prints each measured point while running.
- `ptm validate <recipe>` checks recipe schema, safety limits, ranges, and
  estimated minimum duration without touching hardware.
- `ptm plan <recipe>` prints the planned sweep, safety limits, output
  directory, and a compact point preview without touching hardware.
- `ptm preflight <recipe>` runs validation, checks VISA resources, and probes
  the configured Keithley before measurement.
- Hardware `ptm run <recipe>` repeats preflight and asks for explicit
  confirmation before the Keithley output can be enabled.
- `ptm run <recipe> --yes` skips that interactive confirmation for deliberate
  unattended runs.
- `ptm new-recipe` creates starter YAML recipes for supported sweep modes.
- `ptm run` appends a compact record to `data/run_index.jsonl`.
- `ptm list-runs` shows recent indexed runs.
- `ptm rebuild-index` recreates `data/run_index.jsonl` from existing
  `data/raw/*/metadata.json` files.
- `ptm inspect-run <run_dir>` prints metadata, summary, recipe context, and
  expected file availability for one run.
- Each run folder stores `recipe_snapshot.yaml` and `safety_snapshot.yaml` for
  reproducibility.
- Drain I-V recipes now support `linear_one_way`, `forward_backward`, and
  `multi_segment` sweep modes.
- User interrupts are recorded as partial runs:
  - `interrupted: true`
  - `error_type: KeyboardInterrupt`
  - partial `points.csv`
  - output-off shutdown still runs
- Recipes can now set hardware-facing Keithley options:
  - `instrument.terminal`: `FRONT` or `REAR`
  - `instrument.voltage_range_v`
  - `instrument.current_range_a`
- Metadata now records:
  - `run_dir`
  - `metadata_path`
  - `recipe_path`
  - `recipe.experiment`
  - `instrument_probe`
  - `current_limit_command`
  - `plot_path` when generated
  - `report_path` when generated
  - `recipe_snapshot_path`
  - `safety_snapshot_path`

## Recommended Phase 1 Hardware Check

```powershell
python -m pytest
ptm probe --instrument keithley_2450 --address "GPIB0::2::INSTR"
ptm validate configs/recipes/drain_iv_1k_resistor.yaml
ptm plan configs/recipes/drain_iv_1k_resistor.yaml
ptm preflight configs/recipes/drain_iv_1k_resistor.yaml
ptm new-recipe configs/recipes/my_device_iv.yaml --mode forward_backward --measurement-name my_device_iv --sample-id sample001 --device-id devA
ptm run configs/recipes/drain_iv_1k_resistor.yaml --progress --summary --plot --report
ptm run configs/recipes/drain_iv_1k_resistor.yaml --progress --summary --plot --report --yes
ptm list-runs
ptm inspect-run data\raw\<run_folder>
```

Expected result:

- run completes successfully
- validation reports `Recipe validation: OK`
- plan reports `Measurement plan`, `Sweep`, and `Point preview`
- preflight reports `Preflight OK: True`
- `ptm new-recipe` writes a valid YAML recipe and validates it immediately
- hardware `ptm run` prints the preflight report again and waits at
  `Proceed with hardware output and sweep? [y/N]:`
- entering anything except `y` or `yes` cancels before the run folder is created
- progress prints `[point/total] V=..., I=..., t=...`
- summary prints immediately
- `iv_plot.svg` exists in the new run folder
- `report.md` exists in the new run folder
- `metadata.json` includes `recipe_path`, `recipe.experiment`, `instrument_probe`, and `plot_path`
- `ptm list-runs` shows the latest run with sample/device IDs
- `ptm inspect-run <run_dir>` shows experiment context and file status

## Inspecting A Run

Use this when returning to an older measurement folder:

```powershell
ptm inspect-run data\raw\<run_folder>
```

It reports:

- summary statistics and fitted resistance
- sample/device/operator/tags/notes
- recipe path, safety preset, instrument address, terminal, and sweep
- whether `points.csv`, `metadata.json`, `recipe_snapshot.yaml`,
  `safety_snapshot.yaml`, `iv_plot.svg`, and `report.md` exist

## Run Folder Contents

A complete run folder should contain:

```text
points.csv
metadata.json
recipe_snapshot.yaml
safety_snapshot.yaml
iv_plot.svg
report.md
```

The snapshot files capture the exact parsed recipe and safety preset used for
that run. Keep them with the CSV when archiving or sharing data.

## Markdown Reports

Create a report during a run:

```powershell
ptm run configs/recipes/drain_iv_1k_resistor.yaml --summary --plot --report
```

Or generate one later:

```powershell
ptm report data\raw\<run_folder>
```

The report includes summary statistics, experiment metadata, recipe context,
safety limits, file status, and an embedded `iv_plot.svg` when present.

## Run Index

Each `ptm run` appends one JSON line to:

```text
data/run_index.jsonl
```

This file is ignored by git because it is experiment output. Use:

```powershell
ptm list-runs
ptm list-runs --limit 20
ptm rebuild-index
```

to quickly find recent run folders without browsing `data/raw` manually.
Use `ptm rebuild-index` if the index file was deleted or if older run folders
were created before indexing existed.

Filter indexed runs:

```powershell
ptm list-runs --sample resistor_box
ptm list-runs --device 1k_resistor
ptm list-runs --tag multi-segment
ptm list-runs --completed
ptm list-runs --failed
ptm list-runs --interrupted
```

Filters can be combined, for example:

```powershell
ptm list-runs --sample resistor_box --tag resistor --limit 5
```

## Experiment Metadata

Recipes can include human-facing experiment context:

```yaml
experiment:
  sample_id: resistor_box
  device_id: 1k_resistor
  operator: ""
  notes: Phase 1 hardware smoke test with a 1 kOhm resistor.
  tags:
    - smoke-test
    - resistor
```

This block is included in `metadata.json` and shown by `ptm validate`. Before
real device runs, fill in `sample_id`, `device_id`, and `operator` so saved data
can be traced later.

## Creating Recipe Templates

Create a starter recipe instead of copying YAML by hand:

```powershell
ptm new-recipe configs/recipes/my_device_iv.yaml --mode linear_one_way --measurement-name my_device_iv
ptm new-recipe configs/recipes/my_device_fb.yaml --mode forward_backward --measurement-name my_device_fb --sample-id sample001 --device-id devA
ptm new-recipe configs/recipes/my_device_segments.yaml --mode multi_segment --measurement-name my_device_segments
```

The command refuses to overwrite an existing file unless `--overwrite` is
provided. After writing the file, it runs the same validation report as
`ptm validate`.

## Measurement Plan

Preview the measurement without opening a VISA session:

```powershell
ptm plan configs/recipes/drain_iv_1k_resistor.yaml
```

It reports:

- sample/device/operator/tags
- output directory
- instrument address, terminal, and ranges
- safety preset and current/voltage limits
- sweep mode, point count, voltage span, and estimated minimum duration
- leading and trailing planned points, with the middle omitted for long sweeps

Increase the preview size when checking multi-segment boundaries:

```powershell
ptm plan configs/recipes/drain_iv_1k_multisegment.yaml --preview-points 12
```

Hardware `ptm run` prints this same plan before preflight and confirmation.

## Preflight

Run preflight immediately before a hardware measurement:

```powershell
ptm preflight configs/recipes/drain_iv_1k_resistor.yaml
```

It checks:

- recipe schema and safety limits
- configured VISA address appears in `ptm list-resources`
- Keithley responds to `*IDN?`, `*LANG?`, and `:SYST:ERR?`

Expected final line:

```text
Preflight OK: True
```

Preflight does not run a sweep, but it does open a VISA session and query the
instrument.

## Hardware Run Confirmation

Normal hardware runs now include a final confirmation gate:

```powershell
ptm run configs/recipes/drain_iv_1k_resistor.yaml --progress --summary --plot --report
```

The command first runs the same checks as `ptm preflight`. If they pass, it asks:

```text
Proceed with hardware output and sweep? [y/N]:
```

Only `y` or `yes` continues. Empty input, `n`, or any other response cancels
before the Keithley output is enabled. Use `--yes` for scripted runs after the
recipe, wiring, terminal selection, and safety preset have already been checked:

```powershell
ptm run configs/recipes/drain_iv_1k_resistor.yaml --progress --summary --plot --report --yes
```

Dry-runs skip this prompt:

```powershell
ptm run configs/recipes/drain_iv_1k_resistor.yaml --dry-run --summary --plot --report
```

## Interrupt Behavior

If the user presses `Ctrl+C` during a run, PyTransportMeasure records a partial
run instead of losing context.

Expected metadata:

```json
{
  "completed": false,
  "interrupted": true,
  "error_type": "KeyboardInterrupt",
  "error_message": "Measurement interrupted by user"
}
```

The runner still attempts to set the source voltage to `0 V`, turn output off,
close the instrument session, and save metadata.

## Recipe Hardware Settings

Example:

```yaml
instrument:
  id: keithley_2450
  address: GPIB0::2::INSTR
  timeout_ms: 10000
  terminal: FRONT
  voltage_range_v: 0.2
  current_range_a: 2.0e-4
```

For a 1 kOhm resistor at `+/-0.1 V`, the expected current is about `+/-100 uA`,
so the smoke-test recipe uses a `200 uA` current range and compliance.

If the device is wired to rear terminals, change `terminal: FRONT` to
`terminal: REAR` before running.

## Sweep Modes

### Linear One-Way

```yaml
sweep:
  mode: linear_one_way
  start_v: -0.1
  stop_v: 0.1
  points: 21
  delay_s: 0.05
  current_compliance_a: 2.0e-4
```

### Forward/Backward

```yaml
sweep:
  mode: forward_backward
  start_v: -0.1
  stop_v: 0.1
  points: 21
  delay_s: 0.05
  current_compliance_a: 2.0e-4
```

This expands to 41 measured points: 21 forward points plus 20 return points.
The turn-around endpoint is not duplicated.

### Multi-Segment

```yaml
sweep:
  mode: multi_segment
  delay_s: 0.05
  current_compliance_a: 2.0e-4
  segments:
    - start_v: -0.1
      stop_v: 0.0
      points: 11
    - start_v: 0.0
      stop_v: 0.1
      points: 11
      delay_s: 0.02
```

Adjacent duplicate segment endpoints are measured once. Segment-level `delay_s`
overrides the top-level sweep delay for that segment.

Example recipes:

```text
configs/recipes/drain_iv_1k_forward_backward.yaml
configs/recipes/drain_iv_1k_multisegment.yaml
```

Next workflow layer: batch/session runs are documented in
`docs/phase2_batch_sessions.md`.
