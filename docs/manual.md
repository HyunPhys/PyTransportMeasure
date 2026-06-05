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
| Dual-gate sweep | Dry-run verified; hardware intentionally blocked | `ptm dual-gate-plan`, `ptm dual-gate --dry-run` |
| Dual-gate lock-in sweep | Dry-run verified; preflight/topology-gated; SR860 readout smoke, active-gate smoke, and guarded tiny active sweep available | `ptm dual-gate-lockin-plan`, `ptm dual-gate-lockin-preflight`, `ptm dual-gate-lockin-smoke`, `ptm dual-gate-lockin --dry-run` |
| SR860 / AC lock-in | Conservative two-terminal hardware smoke path available | `ptm ac-lockin-plan`, `ptm ac-lockin-preflight`, `ptm ac-lockin` |
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
  nplc: 1.0
measurement_geometry:
  terminal_count: 2
  method: two_terminal
  notes: Source and measure current through the same Keithley force leads.
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
- `instrument.nplc`: Keithley current integration time in power-line cycles.
- `measurement_geometry`: electrical measurement topology. Keithley-only DC
  runners currently support `two_terminal`. SR860 lock-in voltage readout paths
  can use guarded `four_terminal` geometry when the lock-in is differential
  voltage input `a-b`.
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
ptm single-gate-preflight configs/recipes/single_gate_hardware_smoke.yaml
ptm single-gate configs/recipes/single_gate_hardware_smoke.yaml --dry-run --summary --plot --report --gate-stats --fake-channel-resistance-ohm 1000000 --fake-gate-leak-resistance-ohm 1000000000 --fake-noise-std-a 0
ptm single-gate configs/recipes/single_gate_hardware_smoke.yaml --progress --summary --plot --report --gate-stats
```

Before the hardware command, edit the recipe so `drain_instrument.address` and
`gate_instrument.address` match the two actual Keithleys and are not identical.
The preflight must report `Drain/gate addresses distinct: True`, both
instrument addresses found, and `Single-gate preflight OK: True`.

## Dual-Gate Sweep

The current dual-gate workflow is dry-run verified and hardware-blocked. It is
the first software step toward Hall bar graphene dual-gate scans. The recipe has
separate blocks for drain, gate1, and gate2 instruments, plus separate gate1,
gate2, and drain sweeps.

```powershell
ptm dual-gate-plan configs/recipes/dual_gate_dry_run.yaml
ptm dual-gate configs/recipes/dual_gate_dry_run.yaml --dry-run --summary --plot --report --gate-stats --fake-noise-std-a 0
```

The saved `points.csv` contains one row for each
`gate1 x gate2 x drain` point. Review artifacts include:

- `dual_gate_heatmap.svg`: mean drain current over the gate1/gate2 grid.
- `dual_gate_stats.csv`: per-gate-pair drain current and leakage statistics.
- `dual_gate_report.md`: human-readable run report.

Hardware dual-gate output is intentionally blocked for now:

```powershell
ptm dual-gate configs/recipes/dual_gate_dry_run.yaml
```

This should return a blocking message before any instrument output is enabled.
The next hardware design step is to choose between a DC three-source topology
and an AC topology where the two Keithleys bias the gates while SR860/lock-in
readout measures the source-drain response.

## Dual-Gate Lock-In Sweep

The dual-gate lock-in workflow is the software path closest to the current
hardware set: two Keithley 2450 instruments bias gate1 and gate2, while SR860
readout records the source-drain lock-in response. A guarded 2x2 active sweep
path is available after three-instrument preflight, readout smoke, and
active-gate smoke.

```powershell
ptm dual-gate-lockin-plan configs/recipes/dual_gate_lockin_dry_run.yaml
ptm dual-gate-lockin-preflight configs/recipes/dual_gate_lockin_dry_run.yaml
ptm dual-gate-lockin-smoke configs/recipes/dual_gate_lockin_dry_run.yaml --samples 5 --interval-s 0.2 --progress
ptm dual-gate-lockin-active-smoke configs/recipes/dual_gate_lockin_dry_run.yaml --gate1-v 0.01 --gate2-v 0 --samples 3 --settle-s 0.2 --interval-s 0.2 --progress
ptm dual-gate-lockin configs/recipes/dual_gate_lockin_limited_active.yaml --allow-active-sweep --max-hardware-points 4 --progress --plot --report --gate-stats
ptm dual-gate-lockin configs/recipes/dual_gate_lockin_dry_run.yaml --dry-run --summary --plot --report --gate-stats --fake-noise-std 0
```

The saved `points.csv` contains one row per `gate1 x gate2` pair, with gate
leakage currents, SR860 X/Y/R/theta values, and derived source-drain transport
columns:

- `source_drain_excitation_v`: recipe excitation amplitude.
- `source_drain_nominal_current_a`: excitation amplitude divided by the
  declared current-bias resistor.
- `lockin_resistance_ohm`: `lockin_r_v / source_drain_nominal_current_a`.
- `lockin_conductance_s`: inverse of `lockin_resistance_ohm`.
- `lockin_sheet_resistance_ohm_per_sq`: longitudinal Hall-bar sheet resistance,
  when channel length/width are declared.
- `lockin_sheet_conductivity_s_per_sq`: inverse sheet resistance.
- `lockin_hall_resistance_ohm`: Hall-probe resistance for
  `voltage_probe_role: hall`.
- `lockin_hall_carrier_density_per_m2`: single-field 2D carrier density
  estimate, `B / (e * Rxy)`, when `magnetic_field_t` is declared.

Review artifacts include:

- `dual_gate_lockin_heatmap.svg`: mean lock-in R over the gate1/gate2 grid.
- `dual_gate_lockin_stats.csv`: per-gate-pair lock-in, derived transport, and
  leakage statistics.
- `dual_gate_lockin_report.md`: human-readable run report. It records the
  measurement geometry, lock-in voltage contacts, excitation contacts, and
  source-drain excitation/current assumptions. When longitudinal Hall-bar
  channel geometry is available, it also reports sheet resistance and sheet
  conductivity ranges.

The `topology` block is required for this method:

```yaml
topology:
  device_layout: hall_bar
  gate1_role: top_gate
  gate2_role: back_gate
  source_contact: S
  drain_contact: D
  lockin_input_mode: voltage
  lockin_input_contacts: [Vxx+, Vxx-]
  voltage_probe_role: longitudinal
  channel_length_m: 5.0e-6
  channel_width_m: 2.0e-6
  excitation_source: sr860_sine_out
  excitation_contacts: [S, D]
  excitation_amplitude_v: 0.01
  current_bias_resistor_ohm: 1000000
```

Edit these labels to match the actual Hall bar device before lab hardware
preflight. The plan and preflight reports print this topology before any
hardware output can be considered. The nominal source-drain current is an
analysis value derived from this topology; it assumes the declared bias resistor
dominates the AC excitation path.

For longitudinal voltage probes, set `voltage_probe_role: longitudinal` and
provide both `channel_length_m` and `channel_width_m` from the Hall-bar voltage
probe spacing and channel width. The runner then writes:

- `lockin_sheet_resistance_ohm_per_sq = lockin_resistance_ohm * width / length`
- `lockin_sheet_conductivity_s_per_sq = 1 / lockin_sheet_resistance_ohm_per_sq`

For Hall voltage probes, use `voltage_probe_role: hall` and omit channel
length/width. If `magnetic_field_t` is declared, the runner estimates
`lockin_hall_carrier_density_per_m2 = B / (e * lockin_hall_resistance_ohm)`.
This is a first-pass fixed-field estimate; antisymmetrized Hall extraction and
zero-field offset subtraction are available as saved-run analysis commands.
Mobility extraction can then combine Hall density with longitudinal sheet
conductivity.

To create a consistent Vxx/Vxy Hall-bar recipe set from one verified base
dual-gate lock-in recipe, use:

```powershell
ptm dual-gate-lockin-hall-suite-template configs\recipes\dual_gate_lockin_four_terminal_dry_run.yaml configs\recipes\hall_suite_sampleA --measurement-prefix sampleA_cd1 --magnetic-field-t 1.0 --longitudinal-contact Vxx+ --longitudinal-contact Vxx- --hall-contact Vxy+ --hall-contact Vxy- --channel-length-m 5.0e-6 --channel-width-m 2.0e-6
```

This writes:

- `sampleA_cd1_vxx.yaml`
- `sampleA_cd1_vxy_plus_b.yaml`
- `sampleA_cd1_vxy_minus_b.yaml`
- `sampleA_cd1_vxy_zero_b.yaml`, unless `--no-zero-field` is used
- `sampleA_cd1_review.md`

The generated recipes keep the base gate Keithley, SR860, gate sweep, safety,
and topology wiring assumptions, but set the voltage-probe role, magnetic-field
metadata, voltage contacts, and longitudinal channel dimensions for each run.
The review markdown includes plan/preflight commands, guarded hardware command
templates, and the downstream Hall analysis command sequence.

Before running the generated suite, check that the recipes still agree where
they should:

```powershell
ptm dual-gate-lockin-hall-suite-check configs\recipes\hall_suite_sampleA\sampleA_cd1_vxx.yaml configs\recipes\hall_suite_sampleA\sampleA_cd1_vxy_plus_b.yaml configs\recipes\hall_suite_sampleA\sampleA_cd1_vxy_minus_b.yaml --zero-field-recipe configs\recipes\hall_suite_sampleA\sampleA_cd1_vxy_zero_b.yaml
```

The check verifies shared gate sweeps, Keithley settings, SR860 settings,
safety preset, excitation topology, point count, Hall probe roles, and magnetic
field signs/magnitudes. It does not touch hardware.

To print one aggregate runbook for the whole Hall suite, use:

```powershell
ptm dual-gate-lockin-hall-suite-plan configs\recipes\hall_suite_sampleA\sampleA_cd1_vxx.yaml configs\recipes\hall_suite_sampleA\sampleA_cd1_vxy_plus_b.yaml configs\recipes\hall_suite_sampleA\sampleA_cd1_vxy_minus_b.yaml --zero-field-recipe configs\recipes\hall_suite_sampleA\sampleA_cd1_vxy_zero_b.yaml
```

The suite plan is also hardware-free. It repeats the consistency result, lists
the Vxx/+B/-B/0B measurement order, prints preflight and guarded hardware command
templates, and shows the downstream Hall antisymmetry, zero-field correction,
and mobility commands.

If a dual-gate lock-in scan is interrupted after writing a partial `points.csv`,
resume into a new run directory instead of modifying the old one:

```powershell
ptm dual-gate-lockin configs\recipes\<dual_gate_lockin_recipe>.yaml --dry-run --resume-from-run data\raw\<partial_run_folder>
```

For hardware, keep the usual active-sweep guards:

```powershell
ptm dual-gate-lockin configs\recipes\<dual_gate_lockin_recipe>.yaml --allow-active-sweep --resume-from-run data\raw\<partial_run_folder> --max-hardware-points <N> --hardware-approval-note "<lab note>" --accepted-previous-run data\raw\<accepted_run> --yes --progress --plot --report --gate-stats
```

The resume source must be an incomplete `dual_gate_lockin_sweep` run with a
matching planned gate-grid signature. Its `points.csv` must contain a contiguous
prefix beginning at index 0. The resumed command writes a new run folder, copies
the previous rows first, then measures only the remaining grid points.

When matched `+B` and `-B` Hall runs are available, use:

```powershell
ptm dual-gate-lockin-hall-antisym data\raw\<plus_B_run> data\raw\<minus_B_run> --output-dir data\analysis\<hall_antisym_folder>
```

This writes `hall_antisym.csv`, `hall_antisym_report.md`, and
`hall_antisym_metadata.json`. By default it uses signed `lockin_x_v`, computes
`Rxy_odd = (R(+B) - R(-B)) / 2`, and estimates
`n_2d = |B| / (e * Rxy_odd)`.

When a finite-field Hall run and a matching `B=0` Hall run are available, use:

```powershell
ptm dual-gate-lockin-hall-zero-correct data\raw\<field_B_run> data\raw\<zero_B_run> --output-dir data\analysis\<hall_zero_corrected_folder>
```

This writes `hall_zero_corrected.csv`, `hall_zero_corrected_report.md`, and
`hall_zero_corrected_metadata.json`. It computes
`Rxy_corrected = Rxy(B) - Rxy(0)` and
`n_2d = B / (e * Rxy_corrected)`. Prefer the `+B/-B`
antisymmetrization command when both polarities are available; use zero-field
correction when the measurement set contains a reliable `B=0` Hall offset run.

After a matching longitudinal Vxx dual-gate lock-in run is available, combine
its sheet conductivity with the Hall density:

```powershell
ptm dual-gate-lockin-hall-mobility data\analysis\<hall_density_folder> data\raw\<longitudinal_Vxx_run> --output-dir data\analysis\<hall_mobility_folder>
```

Here `hall_density_folder` can be either a folder containing
`hall_antisym.csv` or a folder containing `hall_zero_corrected.csv`. Passing the
CSV path directly also works.

This writes `hall_mobility.csv`, `hall_mobility_report.md`, and
`hall_mobility_metadata.json`. The command requires the longitudinal run to be
a completed `dual_gate_lockin_sweep` with `voltage_probe_role: longitudinal`.
It computes signed mobility and lab-facing mobility magnitude:

- `mu_signed = sigma_sheet / (e * n_2d)`
- `|mu| = |sigma_sheet| / (e * |n_2d|)`
- `mobility_magnitude_cm2_per_v_s = |mu| * 1e4`

The readout smoke command runs after preflight and saves SR860 X/Y/R/theta
samples to `lockin_smoke.csv`. It does not configure Keithley source mode and
does not enable gate output. Use it to confirm that the SR860 signal path and
front-panel settings make sense before any future active gate sweep.

The active-gate smoke command is the first dual-gate lock-in command that may
enable Keithley gate outputs. It applies one static `gate1/gate2` voltage pair,
records leakage current and SR860 X/Y/R/theta samples to `active_gate_smoke.csv`,
then turns both gate outputs off in normal, error, and interrupt paths. Start
with small voltages and do not use `--yes` until the prompt has been checked on
the lab laptop.

The limited active sweep command enables the full gate1 x gate2 runner only when
`--allow-active-sweep` is supplied and the recipe point count is no larger than
`--max-hardware-points`. Use `configs/recipes/dual_gate_lockin_limited_active.yaml`
for the first guarded 2x2 sweep. The broader dry-run recipe is intentionally
blocked by the default point guard in hardware mode.

The plan and preflight reports include a `Scan readiness` block. Check this
before raising `--max-hardware-points`:

- gate grid and total point count,
- gate1/gate2 voltage step,
- minimum programmed settle time,
- default hardware point guard status,
- nominal source-drain AC current.

If `--max-hardware-points` is raised above the default guard, the CLI requires
both `--hardware-approval-note` and `--accepted-previous-run`. The previous run
must be a saved dual-gate lock-in sweep that passes strict
`ptm dual-gate-lockin-audit`, including SR860 setting readback. The CLI also
checks scale-up compatibility: measurement geometry, topology, lock-in settings,
gate Keithley settings, compliance policy, and whether the candidate grid
contains the accepted previous grid points. The note, accepted-run audit
summary, and compatibility result are saved in `metadata.json` under
`hardware_guard`.
Use this for short lab-context notes such as
`"2x2 smoke passed, leakage < 10 pA, expanding to 5x5"`.

```powershell
ptm dual-gate-lockin configs/recipes/dual_gate_lockin_limited_active.yaml --allow-active-sweep --max-hardware-points 25 --hardware-approval-note "2x2 accepted; expanding to 5x5" --accepted-previous-run data\raw\<accepted_limited_run_folder> --progress --plot --report --gate-stats
```

Before enabling hardware output, you can run the same accepted-run and
scale-up compatibility checks without starting a measurement:

```powershell
ptm dual-gate-lockin-scale-up-check data\raw\<accepted_limited_run_folder> configs/recipes/<candidate_broader_recipe>.yaml
```

The command must print both `Dual-gate lock-in acceptance: PASS` and
`Dual-gate lock-in scale-up compatibility: PASS` before the candidate recipe is
used for a raised-point hardware run.

To reduce manual copy errors, generate a candidate broader recipe from the
accepted run metadata and only change the gate grid:

```powershell
ptm dual-gate-lockin-scale-up-template data\raw\<accepted_limited_run_folder> configs/recipes/dual_gate_lockin_3x3_candidate.yaml --gate1-start-v -0.1 --gate1-stop-v 0.1 --gate1-points 3 --gate2-start-v -0.1 --gate2-stop-v 0.1 --gate2-points 3 --measurement-name dual_gate_lockin_3x3_candidate
```

The template command writes the candidate recipe, writes a companion
`dual_gate_lockin_3x3_candidate.review.md`, and immediately runs the same
hardware-free scale-up check. The review file contains the scale-up check
command, preflight command, hardware run command template, and full candidate
plan. Use `--review-path` to choose a different review file or `--no-review`
when scripting.

Dual-gate lock-in active sweep metadata includes recovery checkpoints:
`planned_points`, `points_written`, `remaining_points`, `abort_class`,
`last_completed_index`, last completed gate voltages, `next_point_index`,
`planned_gate_grid`, `planned_gate_grid_signature`, `outputs_off_after_run`,
and `recovery_recommendation`. The grid signature is a hash of the ordered
gate1 x gate2 voltage grid; use it to confirm that a saved partial or accepted
run belongs to the same scan plan before comparing or expanding runs. Current
policy is manual review plus restart from the beginning, not automatic resume.
If `abort_class` is `safety_stop`, do not resume until the leakage/compliance
cause has been reviewed.

Broad hardware scans are intentionally blocked by default:

```powershell
ptm dual-gate-lockin configs/recipes/dual_gate_lockin_dry_run.yaml
```

The blocked hardware command prints the same preflight report before returning.
Use the limited active recipe first, and only raise `--max-hardware-points`
after the lab smoke checklist, saved recovery metadata, and strict acceptance
audit look correct.

After a limited active sweep, audit the saved run before expanding the grid:

```powershell
ptm dual-gate-lockin-audit data\raw\<dual_gate_lockin_run_folder> --write-report
```

The audit requires a completed dual-gate lock-in sweep, complete point count,
matched gate1/gate2 Keithley configuration readback, explicit Keithley NPLC,
confirmed 0 V before output-off cleanup, and SR860 setting readback that
matches the recipe. Newer run metadata also lets the audit verify that
`points.csv` follows the saved ordered gate grid and that the grid signature
matches. The audit also prints gate1/gate2 leakage maxima and each
leakage/compliance margin. If the margin is below 10x, the run can still pass
when no compliance was hit, but that warning blocks `dual-gate-lockin-scale-up-check`
and raised-point hardware runs until another limited run has comfortable leakage
margin. A `PASS` result without scale-up-blocking warnings is the artifact-level
checkpoint for deciding whether the next hardware grid can be larger.

Active dual-gate lock-in runners repeat the SR860 setting check after connecting
to the lock-in and before enabling either gate output. When the SR860 probe
returns `setting_*` readback fields, metadata records
`lockin_settings_readback_available`, `lockin_settings_readback_check`,
`lockin_settings_readback_matched`, and `lockin_settings_readback_enforced`. If
the readback contradicts the recipe, the run stops with
`triggered_limit: lockin_settings_readback` before gate output turns on.

For dry-run artifact checks only, fake SR860 metadata can be relaxed:

```powershell
ptm dual-gate-lockin-audit data\raw\<dry_run_folder> --allow-missing-lockin-settings
```

Four-terminal lock-in dry-run recipes are available for Hall-bar planning:

```powershell
ptm ac-lockin-plan configs/recipes/ac_lockin_four_terminal_dry_run.yaml
ptm ac-lockin configs/recipes/ac_lockin_four_terminal_dry_run.yaml --dry-run --summary --plot --report --fake-noise-std 0
ptm dual-gate-lockin-plan configs/recipes/dual_gate_lockin_four_terminal_dry_run.yaml
ptm dual-gate-lockin configs/recipes/dual_gate_lockin_four_terminal_dry_run.yaml --dry-run --summary --plot --report --gate-stats --fake-noise-std 0
```

For `four_terminal` lock-in recipes, the SR860 recipe block must use
`input_mode: voltage` and `voltage_input: a-b`. Dual-gate Hall-bar lock-in
recipes also require two distinct `topology.lockin_input_contacts`, two distinct
`topology.excitation_contacts`, and no overlap between those voltage and
excitation contacts. Reports generated from these runs include the same context
so an exported run folder remains interpretable even away from the recipe file.

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

The current AC / lock-in workflow has a conservative two-terminal hardware smoke
path. It validates the recipe, fake-lock-in readout, CSV columns, metadata,
summary, plot, and report flow, and can run Keithley source bias plus SR860
X/Y/R/theta readout after preflight.

```powershell
ptm ac-lockin-plan configs/recipes/ac_lockin_dry_run.yaml
ptm ac-lockin configs/recipes/ac_lockin_dry_run.yaml --dry-run --summary --plot --report --fake-resistance-ohm 1000000 --fake-lockin-r-v 0.000002 --fake-lockin-phase-deg 30 --fake-noise-std 0
```

Before hardware:

```powershell
ptm ac-lockin-plan configs/recipes/ac_lockin_hardware_smoke.yaml
ptm ac-lockin-preflight configs/recipes/ac_lockin_hardware_smoke.yaml
ptm ac-lockin configs/recipes/ac_lockin_hardware_smoke.yaml --progress --summary --plot --report
```

SR860 expected settings are written in the `lockin` block:

```yaml
lockin:
  enabled: true
  id: srs_sr860
  address: GPIB0::4::INSTR
  read_timing: after_dc_settle
  reference_source: internal
  reference_frequency_hz: 17.777
  sine_output_amplitude_v: 0.01
  input_mode: voltage
  voltage_input: a
  input_coupling: ac
  input_grounding: float
  voltage_input_range_v: 0.01
  sensitivity_index: 18
  time_constant_index: 10
  settle_time_constants: 3.0
  filter_slope_db_per_oct: 24
  synchronous_filter: false
```

These values are recorded in recipe snapshots, plan output, and metadata. AC
and dual-gate lock-in preflight also query the current SR860 settings with
read-only commands and compare them against these recipe values. A mismatch in
declared reference frequency, sine amplitude, input mode, input range,
sensitivity, time constant, filter slope, or synchronous filter blocks the
preflight before any Keithley output is enabled.

`ptm ac-lockin` repeats this readback check inside the runner after connecting
to the SR860 and before enabling Keithley source output. When SR860 setting
readback is available, metadata records `lockin_settings_readback_available`,
`lockin_settings_readback_check`, `lockin_settings_readback_matched`, and
`lockin_settings_readback_enforced`. If the runtime readback contradicts the
recipe, the run stops with `triggered_limit: lockin_settings_readback` before
source output turns on.

For hardware lock-in reads, the runner can wait after the DC/gate settle and
before `SNAP?`/`OUTP?` readout. Set `settle_time_constants` to derive this
delay from the SR860 `time_constant_index`, or set `read_settle_s` for an
explicit seconds override. For example, `time_constant_index: 10` is 0.1 s on
the SR860, so `settle_time_constants: 3.0` adds a 0.3 s lock-in read settle per
point. Plan and metadata output include `lockin_time_constant_s` and
`lockin_read_settle_s`.

Current hardware code reads SR860 channels and setting readback but does not
reset or reconfigure the SR860. Adjust the SR860 front panel manually until the
preflight `Lock-in setting check` reports all expected settings match. Automatic
SR860 configuration remains a later smoke-tested phase.

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
editing, a method-aware Recipe Overview, schema validation, saving edited
recipes, schema-driven Recipe Form editing, plan preview, dry-run execution,
summary, metadata, in-app points-based plot preview, report preview, indexed run
browsing, opening generated run artifacts, editor-backed plan/dry-run, lab
doctor, Drain I-V preflight, and guarded Drain I-V hardware runs with progress
streaming and persistent GUI session logs. The GUI is organized into
`Measurement`, `Instruments`, and `Analysis` workspaces. `Measurement >
Workflow` shows the major preparation steps and the next recommended action.

Recommended GUI workflow:

1. Open `Measurement > Workflow`.
2. Open `Measurement > Recipe Overview` and confirm the method, experiment
   metadata, instrument blocks, sweep/pulse blocks, output, and checks.
3. Click `Check YAML`.
4. Open `Instruments`, click `Refresh Instruments`, select the intended VISA
   address, and click `Test Selected Address`.
5. Return to `Measurement`, click `Plan`, and inspect the sweep.
6. Run `Dry Run` and inspect the live plot and generated artifacts.
7. On the lab laptop, click `Preflight` immediately before hardware.
8. Click `Hardware Run` only after the confirmation dialog matches the wiring
   and recipe.

The workflow guide marks completed steps with `[x]`. Editing YAML or the
structured form resets recipe-dependent steps, while instrument refresh and
communication-test state remain visible for the current session.

`Dry-run Model` is collapsed by default. Expand it only when fake resistance,
noise, gate modulation, or lock-in simulation values need editing. The expanded
settings area is scrollable so it remains readable in short windows.

`Stop Run` is enabled during GUI dry-runs and guarded Drain I-V hardware runs.
It requests a cooperative stop at the next safe runner checkpoint. Interrupted
runs keep partial CSV/metadata artifacts, set `interrupted: true`, and still use
the runner cleanup path that turns Keithley output off.

Recipe Form workflow:

1. Select a measurement method.
2. Open `Recipe Form`.
3. Click `YAML -> Form` if the form should be rebuilt from the current YAML
   editor text.
4. Edit method-specific fields such as experiment metadata, instrument blocks,
   sweep settings, pulse settings, lock-in settings, safety preset, output
   directory, and optional quality checks.
5. Click `Form -> YAML`.
6. Click `Check YAML`.
7. Click `Plan` to preview the current editor draft.
8. Run a dry-run before saving or running the recipe on hardware.

The schema-driven Recipe Form supports Drain I-V, single-gate, AC lock-in, and
pulse recipes. Advanced YAML remains available for complex fields that are not
comfortable to edit in a simple form.

Recipe editing workflow:

1. Select the measurement method.
2. Edit the YAML in `Recipe YAML`.
3. Click `Plan` or `Dry Run` to use the current unsaved editor contents.
4. Open `Instruments`, click `Refresh Instruments`, and select the intended
   VISA address.
5. Click `Test Selected Address` for a quick communication probe, or
   `Full Doctor` for the full lab-laptop diagnostic.
6. Return to `Measurement` and click `Preflight` to check recipe safety and
   probe readiness.
7. Click `Check YAML`.
8. Click `Save YAML As` if the draft should become a persistent recipe file.

Recipe tool button meanings:

- `Open Recipe File`: read the YAML file from the recipe path field into the
  editor.
- `Check YAML`: validate the current editor YAML against recipe schema and
  safety rules.
- `Save YAML As`: write the current editor YAML to a chosen file.
- `YAML -> Form`: parse the current YAML editor text and rebuild the method
  form from the recipe schema.
- `Form -> YAML`: regenerate the YAML editor contents from the schema-driven
  form, then validate it through the method recipe model.

`Recipe Overview` is read-only and updates from the current YAML editor text. It
is for quick structural inspection; `Plan` remains the exact sweep and safety
preview before a run.

Lab context metadata:

The `experiment` block can include `sample_id`, `device_id`, `cooldown_id`,
`contact_geometry`, `contact_notes`, `lab_notebook_ref`, `operator`, `notes`,
and `tags`. These fields do not change the measurement. They are saved into
metadata, validation output, reports, and the run index so a run can be traced
back to the actual device state and lab notebook.

CLI starter recipes can include this context:

```powershell
ptm new-recipe configs/recipes/my_device_iv.yaml --measurement-name my_device_iv --sample-id sample001 --device-id devA --cooldown-id cd-1 --contact-geometry "2-probe wirebond" --lab-notebook-ref "ELN-1 p.2"
```

The GUI status under `Recipe Tools` tracks this relationship. If YAML is edited,
YAML remains the execution source and the form may be stale. If the form is
edited, those values are not used until `Form -> YAML` regenerates the YAML.

Measurement geometry:

`experiment.contact_geometry` describes the sample/contact state, such as Hall
bar, 2-probe wirebond, contact pads, or cooldown notes. `measurement_geometry`
describes the electrical method the software is expected to execute. For
Keithley-only DC runners this should remain:

```yaml
measurement_geometry:
  terminal_count: 2
  method: two_terminal
  notes: Source and measure through the same force/current path.
```

Four-terminal lock-in recipes are now supported for guarded SR860 voltage
readout paths:

```yaml
measurement_geometry:
  terminal_count: 4
  method: four_terminal
  notes: SR860 reads differential voltage contacts while another path excites current.
```

The safety gate allows this only for lock-in runners with `lockin.input_mode:
voltage` and `lockin.voltage_input: a-b`. For dual-gate Hall-bar lock-in, the
topology must also declare two voltage contacts and two excitation contacts with
no overlap. Keithley 2450 remote-sense / 4-wire DC measurement remains a future
runner and is still blocked by the DC Drain I-V, single-gate, dual-gate, and
pulse paths.

`Plan` and `Dry Run` use the current editor YAML. The recipe path field is used
for loading and saving recipes. GUI dry-runs write a temporary draft recipe under
`data/gui_drafts` before calling the same core runner used by the CLI.

Scheme Builder workflow:

1. Open `Schemes`.
2. Edit the scheme name and step table.
3. Use step type `drain_iv` for a Drain I-V recipe, `single_gate` for a
   single-gate recipe, or `batch` for a batch YAML.
4. Enter the recipe or batch path relative to the scheme YAML location, such as
   `../recipes/drain_iv_1k_resistor.yaml`.
5. For `drain_iv` rows, optionally fill override columns such as `Suffix`,
   `Start V`, `Stop V`, `Points`, `Delay s`, or `Compliance A`.
6. Click `Form -> Scheme YAML`.
7. Click `Check Scheme`.
8. Click `Scheme Plan` and inspect the expanded workflow.
9. Click `Dry Run Scheme` to execute the scheme with fake instruments.
10. Inspect `Result` and `Report`.
11. Use `Scheme Folder` or `Scheme Report` to open saved artifacts.
12. Click `Save Scheme As` only after validation passes.

Saved Scheme Browser workflow:

1. Open `Schemes`.
2. Set `Saved source` to `data/schemes` or another parent folder.
3. Optionally set saved filters by name, status, QC, or dry-run/hardware flag.
4. Click `Refresh Saved`.
5. Select a row in `Saved`.
6. Click `Load Selected`.
7. Inspect `Result` and `Report`.
8. Use `Scheme Folder` to open the selected saved scheme directory.
9. Use `Scheme Report` when the saved scheme has a `scheme_report.md` file.

The GUI remembers the latest run and scheme source folders in
`data/gui_state.json`. If the file is missing or invalid, the GUI falls back to
`data/raw` and `data/schemes`.

Scheme Comparison workflow:

1. Open `Schemes`.
2. Click `Refresh Saved`.
3. Select one or more rows in `Saved`.
4. Click `Compare Selected`.
5. Open `Compare`.
6. Sort the table by `Mean R`, `Rel Std %`, `QC FAIL`, or another column.
7. Click `Export CSV` to save the current comparison rows.
8. Use the table to decide which scheme/step should be inspected in more
   detail.

Scheme Overlay workflow:

1. Open `Schemes`.
2. Click `Refresh Saved`.
3. Select a saved scheme with Drain I-V-style runs.
4. Click `Load Selected`.
5. Open `Overlay`.
6. Resize the window and confirm the plot redraws without image stretching.

Drain I-V overrides let one base recipe be reused for several sweep conditions
without copying the recipe file. For example, a row can set `Suffix` to
`_small`, `Start V` to `-0.05`, `Stop V` to `0.05`, and `Points` to `5`.

The GUI Scheme Builder currently creates, validates, previews, dry-runs, and
reviews scheme YAML. `Dry Run Scheme` uses the fake settings under `Dry-run
Model`, writes a draft scheme under `data/gui_drafts/schemes`, and stores
scheme artifacts under `data/schemes`. Dry-run intervals are skipped so the GUI
can validate the workflow quickly. The `Saved` table reloads previous
`scheme_summary.json` files from the selected source folder, including nested
batch run counts when a linked batch summary is available. `Compare Selected`
uses the same scheme statistics path as CLI review exports, so GUI comparison
values stay consistent with `ptm scheme-stats`. `Overlay` redraws saved
`points.csv` data directly on the GUI canvas instead of embedding
`scheme_overlay.svg`. `Export CSV` writes the comparison rows currently produced
by the GUI comparison service.

Hardware scheme execution remains a CLI workflow until separate lab smoke tests
gate it:

```powershell
ptm scheme-plan configs/schemes/<scheme>.yaml
ptm scheme configs/schemes/<scheme>.yaml --dry-run --summary --plot --report --scheme-runs --scheme-points --scheme-stats
```

Preflight workflow:

1. Confirm the Keithley is in SCPI mode.
2. Confirm the expected VISA address is in the YAML editor.
3. Open `Instruments`, click `Refresh Instruments`, and confirm the expected
   address is listed.
4. Select the address, click `Test Selected Address`, and confirm `OK: True`.
5. Return to `Measurement` and click `Preflight`.
6. Open the `Preflight` subtab.
7. Confirm `Recipe address found: True` and `Preflight OK: True`.

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

To stop an active GUI Drain I-V run, click `Stop Run` once and wait for the
runner to finish cleanup. Test this on the 1 kOhm resistor setup before relying
on it with a real device.

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
3. Use `Source Folder` when runs are stored outside the default `data/raw`
   folder. The source can be a parent folder containing many runs or one saved
   run folder containing `metadata.json`.
4. Optionally fill sample, device, cooldown, tag, method, or status filters.
5. Click `Refresh Runs`.
6. Click table headers to sort the run list.
7. Select a saved run.
8. Click `Load Selected`.
9. Confirm the loaded row is highlighted in light blue.
10. Open `Plot` to inspect a points-based GUI plot that is redrawn on resize.
11. Use `Run Folder`, `Plot`, `Report`, or `Feedback Bundle` to open/export
   artifacts externally.

Use `Clear Filters` to return to the recent unfiltered run list. The run table
shows status, sample, device, cooldown, notebook reference, and tags from the run
index.

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

4-probe, broader SR860/lock-in measurement geometries, pulse hardware, and
additional GUI hardware workflows should be added as method-specific
capabilities after manual command review, fake-driver support, recipe
validation, and smoke tests. See
`docs/phase16_method_extensibility_roadmap.md`,
`docs/phase20_4probe_remote_sense_design.md`,
`docs/phase21_lockin_foundation.md`, and
`docs/phase22_ac_lockin_recipe_skeleton.md`.

For SR860 communication smoke tests, use the manual-backed read-only probe path:

```powershell
ptm identify --instrument srs_sr860 --address "GPIB0::4::INSTR"
ptm probe --instrument srs_sr860 --address "GPIB0::4::INSTR"
ptm doctor --instrument srs_sr860 --address "GPIB0::4::INSTR"
ptm ac-lockin-preflight configs/recipes/ac_lockin_dry_run.yaml
```

Keithley 2450 source blocks should explicitly set `voltage_range_v`,
`current_range_a`, and `nplc`. NPLC controls current measurement integration
time, while the ranges keep the hardware measurement condition traceable and
avoid accidental autorange behavior:

```yaml
instrument:
  id: keithley_2450
  address: GPIB0::2::INSTR
  voltage_range_v: 0.2
  current_range_a: 1.0e-7
  nplc: 1.0
```

Longer NPLC improves current averaging at the cost of sweep speed. For DC gate
leakage and source-current checks, set NPLC deliberately in every active
Keithley block before a hardware run.

CLI hardware paths now require explicit `voltage_range_v`, `current_range_a`,
and `nplc` before any Keithley output can be enabled. Dry-runs remain allowed
without these values, but real Drain I-V, single-gate, AC lock-in, dual-gate
lock-in active-gate smoke, and dual-gate lock-in active sweeps are blocked
until every active Keithley 2450 block has them.

Keithley source blocks may also set an instrument voltage-source delay:

```yaml
instrument:
  id: keithley_2450
  address: GPIB0::2::INSTR
  nplc: 1.0
  source_delay_s: 0.05
```

This sends `:SOUR:VOLT:DEL <seconds>` and records `source_delay_s` in
`configured_*_smu`. When the Keithley readback is available,
`:SOUR:VOLT:DEL?` is compared against the recipe before output is enabled.
This is separate from Python-side `sweep.delay_s`, `gate_sweep.settle_s`, and
lock-in read-settle timing.

Run metadata also stores the normalized SMU configuration that was passed to
the instrument layer. Look for `configured_smu`, `configured_source_smu`,
`configured_drain_smu`, `configured_gate_smu`, `configured_gate1_smu`, or
`configured_gate2_smu` in `metadata.json`. These snapshots include compliance,
voltage range, current range, terminal selection, NPLC, and source delay, and
are saved even for partial or failed runs.

When the instrument supports it, metadata also stores a best-effort readback
under the matching `configured_*_smu_readback` key. For the Keithley 2450, this
is collected after source/measure configuration and before output is enabled.
Use it to compare intended settings against the instrument response for NPLC,
source delay, range/autorange, terminal, voltage readback, and source current
limit.

If a readback-capable SMU reports a contradiction, the runner saves
`configured_*_smu_readback_check`, raises `SafetyLimitError`, and does not enable
output. This gate protects broader scans from silently running with the wrong
NPLC, source delay, range, terminal, or current limit.

Every active runner also writes `output_state` in `metadata.json`. It records
whether each Keithley role attempted output on, whether it was marked enabled,
whether output off was attempted, and whether cleanup reported `off_after_run`.
For multi-SMU runs, inspect each role separately before repeating a partial or
failed hardware scan.

Cleanup also attempts `set_voltage(0.0)` before output off and records
`zero_before_off_*` fields under each output role. A run is cleanest when every
active role has both `zero_before_off_succeeded: true` and
`off_after_run: true`.

Voltage commands are tracked in the same `output_state` block. Use
`last_commanded_voltage_before_zero_v` to see the final measurement setpoint
before cleanup, and `last_commanded_voltage_v` to confirm the final cleanup
target. In a clean run, the latter should usually be `0.0`.

For the first AC/lock-in hardware smoke test, use:

```powershell
ptm ac-lockin-plan configs/recipes/ac_lockin_hardware_smoke.yaml
ptm ac-lockin-preflight configs/recipes/ac_lockin_hardware_smoke.yaml
ptm ac-lockin configs/recipes/ac_lockin_hardware_smoke.yaml --progress --summary --plot --report
```
