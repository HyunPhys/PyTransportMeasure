# PyTransportMeasure Manual

PyTransportMeasure is a hardware-first transport measurement program. Its first
principle is simple: make the smallest useful measurement work on the real
instrument, then build larger workflows around that verified core.

The current verified hardware core is Keithley 2450 Drain I-V measurement. The
project also includes dry-run simulation, review artifacts, batch runs, scheme
composition, campaign analysis, a dry-run single-gate workflow, a dry-run
AC/lock-in workflow, and a dry-run pulse workflow.

## Philosophy

This project is not a generic plotting script and it is not a GUI-first lab
notebook. It is a measurement framework built around these rules:

- Real hardware behavior has priority over elegant abstractions.
- Every hardware feature should have a dry-run or fake-driver path first.
- Recipes describe intent; runners execute; instrument drivers talk to hardware.
- CLI and future GUI should call the same core API.
- Safety limits are conservative by default.
- Normal completion, errors, safety stops, and interrupts should all leave saved
  artifacts.
- New methods such as 4-probe, AC, lock-in, and pulse should be method modules,
  not scattered flags across the codebase.

## Project Structure

Important folders:

- `configs/recipes`: measurement recipes.
- `configs/safety`: safety presets.
- `configs/batches`: batch/session recipes.
- `configs/schemes`: composed measurement workflows.
- `data/raw`: individual run folders.
- `data/batches`: batch summaries and artifacts.
- `data/schemes`: scheme summaries and artifacts.
- `data/campaigns`: grouped campaign analysis.
- `docs`: manual, checklists, roadmap, phase notes, and SCPI notes.
- `pytransport`: package source code.
- `tests`: automated tests.

Important modules:

- `pytransport/recipes.py`: Pydantic recipe models and YAML loading.
- `pytransport/safety.py`: safety validation.
- `pytransport/instruments`: SMU interfaces, fake SMU, Keithley 2450 driver.
- `pytransport/instruments/base.py`: common SMU and lock-in protocols.
- `pytransport/instruments/fake.py`: fake SMU and fake lock-in dry-run tools.
- `pytransport/runner.py`: Drain I-V runner.
- `pytransport/single_gate.py`: single-gate sweep runner.
- `pytransport/ac_lockin.py`: AC/lock-in dry-run sweep runner.
- `pytransport/pulse.py`: pulse-measurement dry-run runner.
- `pytransport/batch.py`: batch recipe resolution.
- `pytransport/scheme.py`: scheme recipe resolution and overrides.
- `pytransport/method_registry.py`: saved-run summary, plot, report, campaign,
  and plan dispatch by `measurement_type`.
- `pytransport/*_review.py`: summary, plot, report, CSV, and stats exporters.
- `pytransport/cli.py`: `ptm` command-line interface.

## Current Capability Map

| Capability | Status | Main commands |
| --- | --- | --- |
| Lab laptop diagnostics | Offline and hardware-probe capable | `ptm doctor` |
| Keithley 2450 Drain I-V | Hardware verified | `ptm validate`, `ptm plan`, `ptm preflight`, `ptm run` |
| Drain I-V forward/backward and multi-segment | Hardware-ready after plan/preflight | `ptm plan`, `ptm run` |
| Batch sessions | Dry-run and hardware-capable for Drain I-V recipes | `ptm batch`, `ptm batch-report`, `ptm batch-stats` |
| Measurement schemes | Dry-run and hardware-capable for supported nested steps | `ptm scheme-plan`, `ptm scheme` |
| Campaign analysis | Offline artifact analysis | `ptm campaign`, `ptm campaign-bundle` |
| Lab feedback bundle | Offline debugging/review | `ptm feedback-bundle` |
| Single-gate sweep | Dry-run verified; hardware smoke-test recipe prepared | `ptm single-gate-plan`, `ptm single-gate` |
| SR860 / AC lock-in | Dry-run verified; hardware run intentionally blocked | `ptm ac-lockin-plan`, `ptm ac-lockin --dry-run` |
| 4-probe / remote sense | Designed and deferred | No active command |
| Pulse measurement | Dry-run verified; hardware run intentionally blocked | `ptm pulse-plan`, `ptm pulse --dry-run` |
| GUI | Dry-run desktop foundation | `ptm-gui` |

## Installation

From the project root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[test]"
python -m pytest
```

For the desktop GUI:

```powershell
pip install -e ".[gui,test]"
ptm-gui
```

Hardware communication uses PyVISA. For the current lab setup, NI-VISA is the
default backend and the verified Keithley address is usually
`GPIB0::2::INSTR`.

## Core Workflow

Use this order for real measurements:

1. Find the instrument.
2. Probe the instrument.
3. Validate the recipe.
4. Preview the plan.
5. Dry-run if possible.
6. Run hardware.
7. Inspect and analyze artifacts.

Commands:

```powershell
ptm list-resources
ptm probe --instrument keithley_2450 --address "GPIB0::2::INSTR"
ptm validate configs/recipes/drain_iv_1k_resistor.yaml
ptm plan configs/recipes/drain_iv_1k_resistor.yaml
ptm run configs/recipes/drain_iv_1k_resistor.yaml --dry-run --summary --plot --report
ptm run configs/recipes/drain_iv_1k_resistor.yaml --progress --summary --plot --report
```

For the first run of a new recipe, do not use `--yes`. Let the confirmation
prompt force one last manual check before output turns on.

## Drain I-V Recipe

Example:

```yaml
measurement_name: drain_iv_1k_resistor_check
safety_preset: resistor_1k_check
experiment:
  sample_id: resistor_box
  device_id: 1k_resistor
  operator: ""
  notes: Phase 1 hardware smoke test with a 1 kOhm resistor.
  tags:
    - smoke-test
    - resistor
instrument:
  id: keithley_2450
  address: GPIB0::2::INSTR
  timeout_ms: 10000
  terminal: FRONT
  voltage_range_v: 0.2
  current_range_a: 2.0e-4
sweep:
  mode: linear_one_way
  start_v: -0.1
  stop_v: 0.1
  points: 21
  delay_s: 0.05
  current_compliance_a: 2.0e-4
output:
  directory: data/raw
checks:
  require_completed: true
  min_points: 21
  fitted_resistance_ohm:
    min_ohm: 900
    max_ohm: 1100
```

Key fields:

- `measurement_name`: file-friendly run name.
- `safety_preset`: named YAML file under `configs/safety`.
- `instrument.address`: VISA address.
- `instrument.terminal`: usually `FRONT` for the current smoke-test setup.
- `sweep.mode`: currently supports linear one-way, forward/backward, and
  multi-segment Drain I-V workflows.
- `sweep.current_compliance_a`: hardware compliance.
- `checks`: post-run QC expectations.

## Common Commands

Instrument:

```powershell
ptm list-resources
ptm doctor --address "GPIB0::2::INSTR"
ptm identify --instrument keithley_2450 --address "GPIB0::2::INSTR"
ptm probe --instrument keithley_2450 --address "GPIB0::2::INSTR"
```

Recipe:

```powershell
ptm validate configs/recipes/drain_iv.yaml
ptm plan configs/recipes/drain_iv.yaml
ptm preflight configs/recipes/drain_iv.yaml
ptm run configs/recipes/drain_iv.yaml --progress --summary --plot --report
```

Dry-run:

```powershell
ptm run configs/recipes/drain_iv_1k_resistor.yaml --dry-run --fake-resistance-ohm 1000 --fake-noise-std-a 0 --summary --plot --report
```

Saved run review:

```powershell
ptm inspect-run data\raw\<run_folder>
ptm summarize data\raw\<run_folder>
ptm plot data\raw\<run_folder>
ptm report data\raw\<run_folder>
ptm check-run data\raw\<run_folder>
ptm feedback-bundle data\raw\<run_folder>
ptm feedback-bundle data\raw\<run_folder> --extra-file doctor.json
```

## Command Selection

Use this as the practical decision tree:

- Use `ptm doctor` first on the lab laptop when checking environment, VISA, or
  Keithley connection state.
- Use `ptm run` for one Drain I-V recipe.
- Use `ptm batch` when repeating one or more Drain I-V recipes as a session.
- Use `ptm scheme` when combining recipes, batches, or single-gate steps.
- Use `ptm campaign` after runs are finished and you want grouped analysis.
- Use `ptm single-gate` for the two-SMU gate/drain workflow.
- Use `ptm ac-lockin --dry-run` for the current AC/lock-in artifact path.
- Use `ptm pulse --dry-run` for the current pulse-measurement artifact path.
- Use `ptm inspect-run`, `ptm summarize`, `ptm plot`, and `ptm report` on saved
  run folders.
- Use `ptm feedback-bundle` before sending lab-laptop run results for
  debugging or review.
- Add `--extra-file doctor.json` or another diagnostic file when the run needs
  lab-laptop context beyond the saved run folder.

Lab doctor workflow:

```powershell
ptm doctor
ptm doctor --address "GPIB0::2::INSTR"
ptm doctor --address "GPIB0::2::INSTR" --json --output doctor.json
```

Use the doctor report before hardware debugging. If `Address found: False`, fix
the VISA address or connection before running a recipe. If the address is found
but probe fails, inspect Keithley command set, VISA backend, cable, and timeout.

`ptm summarize`, `ptm plot`, and `ptm report` dispatch from the saved
`measurement_type`, so the same commands work for both Drain I-V and single-gate
runs. Method-specific commands such as `ptm single-gate-summary` remain
available for explicit workflows.

Plan commands also dispatch through the method registry internally. That keeps
the CLI command names stable while giving each measurement method one place to
define how its recipe is loaded and how its pre-run plan is displayed.

Index:

```powershell
ptm list-runs
ptm list-runs --measurement-type single_gate_sweep
ptm rebuild-index
```

## Batch

Use a batch when repeating one or more Drain I-V recipes.

```powershell
ptm new-batch configs/batches/my_repeat.yaml --kind repeat --name my_repeat --recipe configs/recipes/my_device_iv.yaml --repeat 3 --interval-s 1.0
ptm batch configs/batches/my_repeat.yaml --dry-run --summary --batch-csv --batch-points --batch-stats
ptm batch-report data\batches\<batch_folder>
ptm batch-plot data\batches\<batch_folder>
```

Batch artifacts live under `data/batches`.

## Scheme

Use a scheme when one measurement workflow should combine multiple steps. A
scheme can include Drain I-V recipes, batches, and single-gate steps.

```powershell
ptm scheme-plan configs/schemes/single_gate_dry_run_scheme.yaml
ptm scheme configs/schemes/single_gate_dry_run_scheme.yaml --dry-run --fake-resistance-ohm 1000 --fake-channel-resistance-ohm 1000000 --fake-noise-std-a 0 --summary --plot --report --gate-stats --scheme-runs --scheme-points --scheme-stats
```

Scheme artifacts live under `data/schemes`.

## Single-Gate Sweep

The current single-gate workflow is dry-run verified. Hardware runs require
separate drain and gate Keithley addresses in the recipe.

```powershell
ptm single-gate-plan configs/recipes/single_gate_dry_run.yaml
ptm single-gate configs/recipes/single_gate_dry_run.yaml --dry-run --summary --plot --report --gate-stats --fake-channel-resistance-ohm 1000000 --fake-noise-std-a 0
ptm single-gate-summary data\raw\<single_gate_run_folder>
ptm single-gate-plot data\raw\<single_gate_run_folder>
ptm single-gate-stats data\raw\<single_gate_run_folder>
ptm single-gate-report data\raw\<single_gate_run_folder>
```

For the first two-SMU hardware smoke test, start from the conservative recipe:

```powershell
ptm single-gate-plan configs/recipes/single_gate_hardware_smoke.yaml
ptm single-gate configs/recipes/single_gate_hardware_smoke.yaml --dry-run --summary --plot --report --gate-stats --fake-channel-resistance-ohm 1000000 --fake-gate-leak-resistance-ohm 1000000000 --fake-noise-std-a 0
ptm single-gate configs/recipes/single_gate_hardware_smoke.yaml --progress --summary --plot --report --gate-stats
```

Before the hardware command, edit the recipe so `drain_instrument.address` and
`gate_instrument.address` match the two actual Keithleys and are not identical.

## Campaign

Use a campaign to collect runs, batches, and schemes into one analysis set.

```powershell
ptm campaign --name my_campaign --completed-only --analytics
ptm campaign --name resistor_pass_only --sample resistor_box --device 1k_resistor --tag resistor --qc-status PASS --completed-only --min-resistance-ohm 900 --max-resistance-ohm 1100 --analytics
ptm campaign-stats data\campaigns\<campaign_folder>
ptm campaign-histogram data\campaigns\<campaign_folder>
ptm campaign-bundle data\campaigns\<campaign_folder>
```

Campaign artifacts live under `data/campaigns`.

## AC / Lock-In Sweep

The current AC / lock-in workflow is dry-run only. It validates the recipe,
fake-lock-in readout, CSV columns, metadata, summary, plot, and report flow.

```powershell
ptm ac-lockin-plan configs/recipes/ac_lockin_dry_run.yaml
ptm ac-lockin configs/recipes/ac_lockin_dry_run.yaml --dry-run --summary --plot --report --fake-resistance-ohm 1000000 --fake-lockin-r-v 0.000002 --fake-lockin-phase-deg 30 --fake-noise-std 0
```

Hardware AC lock-in runs are intentionally blocked until the SR860 command set
is confirmed and a hardware smoke-test recipe is added.

## Pulse Measurement

The current pulse workflow is dry-run only. It validates the recipe, fake SMU
current readout, CSV columns, metadata, summary, plot, and report flow.

```powershell
ptm pulse-plan configs/recipes/pulse_dry_run.yaml
ptm pulse configs/recipes/pulse_dry_run.yaml --dry-run --summary --plot --report --progress --fake-resistance-ohm 1000000 --fake-noise-std-a 0
```

Pulse hardware runs are intentionally blocked until the Keithley pulse command
sequence and timing limitations are reviewed separately.

The intended policy is:

- Treat pulse as its own method family.
- Keep pulse amplitude, width, period, duty cycle, pulse count, and total
  on-time limits explicit in the recipe.
- Add and verify fake pulse data before hardware pulse output is enabled.
- Keep future hardware pulse implementation separate from DC sweep logic.

## Desktop GUI

The GUI is a PySide6 desktop app launched with:

```powershell
ptm-gui
```

The current GUI phase supports method selection, recipe selection, YAML recipe
editing, schema validation, saving edited recipes, plan preview, dry-run
execution, summary, metadata, in-app points-based plot preview, report preview, indexed
run browsing, opening generated run artifacts, structured Drain I-V recipe
editing, editor-backed plan/dry-run, lab doctor, Drain I-V preflight, and
guarded Drain I-V hardware runs with progress streaming and persistent GUI
session logs. The GUI is organized into `Measurement`, `Instruments`, and
`Analysis` workspaces.

Drain I-V form workflow:

1. Select `Drain I-V`.
2. Open `Drain I-V Form`.
3. Edit the address, terminal, voltage/current ranges, sweep, safety preset,
   output directory, and optional quality checks.
4. Click `Apply Form to YAML`.
5. Click `Plan` to preview the current editor draft.
6. Open `Validation` and check that the recipe passes.
7. Run a dry-run before saving or running the recipe on hardware.

Recipe editing workflow:

1. Select the measurement method.
2. Edit the YAML in `Recipe YAML`.
3. Click `Plan` or `Dry Run` to use the current unsaved editor contents.
4. Open `Instruments` and click `Doctor` to check the lab laptop, VISA
   resources, and Keithley probe.
5. Return to `Measurement` and click `Preflight` to check recipe safety and
   probe readiness.
6. Click `Validate YAML`.
7. Click `Save Recipe` if the draft should become a persistent recipe file.

`Plan` and `Dry Run` use the current editor YAML. The recipe path field is used
for loading and saving recipes. GUI dry-runs write a temporary draft recipe under
`data/gui_drafts` before calling the same core runner used by the CLI.

Preflight workflow:

1. Confirm the Keithley is in SCPI mode.
2. Confirm the expected VISA address is in the YAML editor.
3. Open `Instruments`, click `Doctor`, and confirm `OK: True`.
4. Return to `Measurement` and click `Preflight`.
5. Open the `Preflight` subtab.
6. Confirm `Recipe address found: True` and `Preflight OK: True`.

Guarded hardware run workflow:

1. Complete the preflight workflow above.
2. Click `Hardware Run`.
3. Read the confirmation dialog.
4. Confirm the measurement name, VISA address, terminal, sweep span, point
   count, compliance, and safety preset.
5. Click `Yes` only when the wiring and recipe are correct.
6. Wait for the run to finish.
7. Open `Progress` and confirm point lines appear during the run.
8. Open `Live Plot` and confirm points accumulate during the run.
9. Open `Session Log` and confirm Doctor/Preflight/Progress events were saved.
10. Open `Analysis` and inspect `Summary`, `Metadata`, `Plot`, and `Report`.
11. Click `Feedback Bundle` if the run should be shared for review/debugging.

`Hardware Run` reruns preflight immediately before enabling output. If preflight
does not pass, the run is blocked before the Keithley output is enabled. GUI
hardware runs currently support only Keithley 2450 Drain I-V recipes.

Feedback bundle workflow:

```powershell
ptm feedback-bundle data\raw\<run_folder>
```

This creates a folder and ZIP under `data/feedback`. The bundle includes copied
run artifacts, `inspection.txt`, `environment.json`, `quality.txt`, and
`bundle_manifest.json`. In the GUI, run or load a saved run and click `Feedback
Bundle` to create the same ZIP. GUI-created feedback bundles include the current
GUI session log under `extras/`.

To add extra diagnostic files from the CLI:

```powershell
ptm feedback-bundle data\raw\<run_folder> --extra-file doctor.json
```

GUI session log workflow:

1. Launch `ptm-gui`.
2. Open `Session Log` and confirm `GUI session started`.
3. Run `Doctor`, `Preflight`, `Dry Run`, or guarded `Hardware Run`.
4. Confirm the Session Log tab records the same major events and progress lines.
5. Use `Open Log` to open the log folder, or click `Feedback Bundle` after a
   run to include the log automatically.

Run browsing workflow:

1. Open `Analysis`.
2. Open the `Runs` subtab.
3. Click `Refresh Runs`.
4. Select a saved run.
5. Click `Load Selected`.
6. Open `Plot` to inspect a points-based GUI plot that is redrawn on resize.
7. Use `Run Folder`, `Plot`, `Report`, or `Feedback Bundle` to open/export
   artifacts externally.

The GUI calls the same core recipe, runner, safety, method registry, quality,
and artifact APIs as the CLI instead of reimplementing measurement logic.

## Output Files

An individual run usually contains:

- `points.csv`: point-by-point measured data.
- `metadata.json`: recipe, safety, completion state, errors, and artifact paths.
- `recipe_snapshot.yaml`: copied recipe at run time.
- `safety_snapshot.yaml`: copied safety preset at run time.
- `summary.json`: computed run summary.
- `plot.svg`: plot artifact.
- `report.md`: human-readable report.

Batch, scheme, and campaign folders contain corresponding summary JSON, report,
CSV, plot, and bundle files.

## Safety Behavior

The current safety posture is conservative:

- Hardware output turns off after normal completion.
- Hardware output turns off after safety stop, error, or keyboard interrupt.
- Partial data is saved when a run stops early.
- Software current limits stop the run.
- Hardware compliance is treated as a limit event.
- Hardware runs are preflight-gated and ask for confirmation unless `--yes` is
  passed.

## Future Method Policy

4-probe, active SR860 hardware acquisition, pulse hardware, and GUI workflows
should be added as method-specific capabilities after manual command review,
fake-driver support, recipe validation, and smoke tests. See
`docs/phase16_method_extensibility_roadmap.md`,
`docs/phase20_4probe_remote_sense_design.md`,
`docs/phase21_lockin_foundation.md`, and
`docs/phase22_ac_lockin_recipe_skeleton.md`.
