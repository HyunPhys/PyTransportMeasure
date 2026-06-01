# PyTransportMeasure Checklists

This document is the practical checklist for running and extending
PyTransportMeasure. Use the smallest checklist that matches the task.

## Current Phase Snapshot

- [x] Keithley 2450 Drain I-V hardware smoke test is working.
- [x] Drain I-V summary, plot, report, and quality checks are available.
- [x] Batch, scheme, and campaign review flows are available.
- [x] Single-gate workflow is dry-run verified.
- [x] SR860 / AC lock-in workflow is dry-run verified.
- [ ] Single-gate two-SMU hardware smoke test still needs lab confirmation.
- [ ] SR860 hardware acquisition is intentionally blocked until command review
  and smoke testing.
- [x] Pulse measurement is dry-run verified; hardware output is intentionally
  blocked.
- [x] PySide6 GUI foundation supports plan preview and dry-run artifacts.
- [x] GUI recipe builder foundation supports YAML edit, validation, and save.
- [x] GUI run browser can load indexed runs and open artifacts.
- [ ] 4-probe / remote sense is documented as TODO, not implemented.
- [ ] GUI hardware runs and form-based recipe builder are future milestones.

## Daily Setup

- [ ] Activate the Python environment.
  ```powershell
  .\.venv\Scripts\Activate.ps1
  ```
- [ ] Confirm the package is installed in editable mode after code changes.
  ```powershell
  pip install -e ".[test]"
  ```
- [ ] Run the test suite before touching hardware.
  ```powershell
  python -m pytest
  ```
- [ ] Confirm the Keithley is in SCPI mode when using the 2450 driver.
- [ ] Confirm the expected VISA address.
  ```powershell
  ptm list-resources
  ```

## New Drain I-V Recipe

- [ ] Start from a known-good recipe.
  ```powershell
  ptm new-recipe configs/recipes/my_device_iv.yaml --mode linear_one_way --measurement-name my_device_iv --sample-id sample001 --device-id devA
  ```
- [ ] Edit `measurement_name`, `experiment`, `instrument.address`,
  `instrument.terminal`, sweep range, compliance, and output directory.
- [ ] Choose a conservative safety preset.
- [ ] Validate the recipe.
  ```powershell
  ptm validate configs/recipes/my_device_iv.yaml
  ```
- [ ] Preview the exact voltage points.
  ```powershell
  ptm plan configs/recipes/my_device_iv.yaml
  ```
- [ ] Dry-run the full artifact path.
  ```powershell
  ptm run configs/recipes/my_device_iv.yaml --dry-run --summary --plot --report
  ```

## 1 kOhm Resistor Hardware Smoke Test

- [ ] Connect the 1 kOhm resistor before connecting a real device.
- [ ] Confirm the VISA resource appears.
  ```powershell
  ptm list-resources
  ```
- [ ] Probe the Keithley.
  ```powershell
  ptm probe --instrument keithley_2450 --address "GPIB0::2::INSTR"
  ```
- [ ] Validate, plan, and preflight the resistor recipe.
  ```powershell
  ptm validate configs/recipes/drain_iv_1k_resistor.yaml
  ptm plan configs/recipes/drain_iv_1k_resistor.yaml
  ptm preflight configs/recipes/drain_iv_1k_resistor.yaml
  ```
- [ ] Run with progress and review artifacts.
  ```powershell
  ptm run configs/recipes/drain_iv_1k_resistor.yaml --progress --summary --plot --report
  ```
- [ ] Confirm the expected result:
  - [ ] `completed=True`
  - [ ] `points=21`
  - [ ] fitted resistance is near `1000 ohm`
  - [ ] current at `0.1 V` is near `1e-4 A`

## Real Device Drain I-V

- [ ] Pass the 1 kOhm smoke test in the same session.
- [ ] Confirm wiring, terminal selection, compliance, and voltage range manually.
- [ ] Use `ptm plan` and inspect every voltage endpoint.
- [ ] Use `ptm preflight` immediately before the run.
- [ ] Run without `--yes` for the first run so the confirmation prompt remains.
  ```powershell
  ptm run configs/recipes/my_device_iv.yaml --progress --summary --plot --report
  ```
- [ ] Inspect the run directory.
  ```powershell
  ptm inspect-run data\raw\<run_folder>
  ptm check-run data\raw\<run_folder>
  ```
- [ ] Confirm output is off after normal completion, error, or interrupt.

## Batch / Scheme Workflow

- [ ] Create or edit a batch when repeating one recipe.
  ```powershell
  ptm new-batch configs/batches/my_repeat.yaml --kind repeat --name my_repeat --recipe configs/recipes/my_device_iv.yaml --repeat 3 --interval-s 1.0
  ```
- [ ] Create or edit a scheme when combining recipes, batches, or single-gate
  steps.
  ```powershell
  ptm new-scheme configs/schemes/my_scheme.yaml --kind recipe_and_batch --name my_scheme --recipe configs/recipes/my_device_iv.yaml --batch configs/batches/my_repeat.yaml
  ```
- [ ] Preview the scheme before running.
  ```powershell
  ptm scheme-plan configs/schemes/my_scheme.yaml
  ```
- [ ] Dry-run the scheme when possible.
  ```powershell
  ptm scheme configs/schemes/my_scheme.yaml --dry-run --summary --plot --report --scheme-runs --scheme-points --scheme-stats
  ```
- [ ] Hardware-run only after every nested recipe has a valid plan and safety
  setting.

## Single-Gate Hardware Smoke Test

- [ ] Confirm two Keithley 2450 instruments are connected and in SCPI mode.
- [ ] Confirm both addresses appear.
  ```powershell
  ptm list-resources
  ```
- [ ] Edit `configs/recipes/single_gate_hardware_smoke.yaml` with the real drain
  and gate VISA addresses.
- [ ] Confirm the drain and gate addresses are different.
- [ ] Preview the exact two-SMU plan.
  ```powershell
  ptm single-gate-plan configs/recipes/single_gate_hardware_smoke.yaml
  ```
- [ ] Dry-run the recipe and artifacts.
  ```powershell
  ptm single-gate configs/recipes/single_gate_hardware_smoke.yaml --dry-run --summary --plot --report --gate-stats --fake-channel-resistance-ohm 1000000 --fake-gate-leak-resistance-ohm 1000000000 --fake-noise-std-a 0
  ```
- [ ] Run the first hardware smoke test without `--yes`.
  ```powershell
  ptm single-gate configs/recipes/single_gate_hardware_smoke.yaml --progress --summary --plot --report --gate-stats
  ```
- [ ] Confirm both Keithley outputs are off after the run.

## Future 4-Probe / Remote-Sense Smoke Test

This checklist is for the future implementation. The current code does not yet
enable 4-probe mode.

- [ ] Confirm the future recipe explicitly states `remote_4wire`.
- [ ] Confirm the plan prints the selected sense mode before hardware access.
- [ ] Use a known resistor or resistor network before a real device.
- [ ] Confirm SCPI mode with `ptm probe`.
- [ ] Confirm front or rear terminal selection; do not mix terminal panels.
- [ ] Connect FORCE HI/LO and SENSE HI/LO correctly.
- [ ] Confirm sense leads are attached close to the DUT.
- [ ] Compare against a 2-wire baseline.
- [ ] Confirm output-off behavior after completion, stop, and interrupt.

## Future SR860 / Lock-In Smoke Test

This checklist is for a future active lock-in method. The current runners do not
read SR860 hardware data yet, but `ptm ac-lockin --dry-run` validates the
artifact path.

- [ ] Confirm the SR860 VISA resource appears in `ptm list-resources`.
- [ ] Confirm the active method recipe owns the lock-in block.
- [ ] Confirm the timing mode is explicit, starting with `after_dc_settle`.
- [ ] Dry-run with `FakeLockIn`.
  ```powershell
  ptm ac-lockin configs/recipes/ac_lockin_dry_run.yaml --dry-run --summary --plot --report --fake-resistance-ohm 1000000 --fake-lockin-r-v 0.000002 --fake-lockin-phase-deg 30 --fake-noise-std 0
  ```
- [ ] Verify `lockin_x_v`, `lockin_y_v`,
  `lockin_r_v`, and `lockin_theta_deg` columns.
- [ ] Confirm lock-in readout appears in summary/report artifacts.
- [ ] Confirm source instruments still turn off after completion, stop, and
  interrupt.

## Pulse Measurement Dry-Run Checklist

Use this checklist before pulse hardware work begins.

- [ ] Confirm pulse remains a separate method, not a flag inside Drain I-V.
- [ ] Confirm the recipe declares base voltage, pulse voltage, width, period,
  duty cycle, pulse count, compliance, and total on-time limits.
- [ ] Preview the plan.
  ```powershell
  ptm pulse-plan configs/recipes/pulse_dry_run.yaml
  ```
- [ ] Dry-run with fake pulse data before enabling hardware output.
  ```powershell
  ptm pulse configs/recipes/pulse_dry_run.yaml --dry-run --summary --plot --report --progress --fake-resistance-ohm 1000000 --fake-noise-std-a 0
  ```
- [ ] Confirm `points.csv` contains one row per acquired pulse point.
- [ ] Confirm `metadata.json` records `completed`, `triggered_limit`, and error
  fields for partial runs.
- [ ] Confirm generic saved-run commands work.
  ```powershell
  ptm inspect-run data\raw\<pulse_run_folder>
  ptm summarize data\raw\<pulse_run_folder>
  ptm plot data\raw\<pulse_run_folder>
  ptm report data\raw\<pulse_run_folder>
  ```
- [ ] Confirm non-dry-run hardware pulse is blocked.
  ```powershell
  ptm pulse configs/recipes/pulse_dry_run.yaml
  ```
- [ ] For a future hardware phase, confirm a safety stop turns the source output
  off and saves partial data.
- [ ] For a future hardware phase, use a resistor load before a real device.
- [ ] Only after dry-run and resistor tests pass, attempt a device pulse test.

## After A Measurement Session

- [ ] List recent runs.
  ```powershell
  ptm list-runs
  ```
- [ ] Regenerate missing artifacts when needed.
  ```powershell
  ptm summarize data\raw\<run_folder>
  ptm plot data\raw\<run_folder>
  ptm report data\raw\<run_folder>
  ```
- [ ] Create a campaign for grouped analysis.
  ```powershell
  ptm campaign --name my_campaign --completed-only --analytics
  ```
- [ ] Bundle the campaign when sharing or archiving.
  ```powershell
  ptm campaign-bundle data\campaigns\<campaign_folder>
  ```

## GUI Dry-Run Checklist

- [ ] Install the GUI extra.
  ```powershell
  pip install -e ".[gui,test]"
  ```
- [ ] Launch the desktop app.
  ```powershell
  ptm-gui
  ```
- [ ] Select each dry-run method at least once:
  - [ ] Drain I-V
  - [ ] Single-gate sweep
  - [ ] AC lock-in sweep
  - [ ] Pulse measurement
- [ ] Click `Plan` and confirm the plan text matches the selected recipe.
- [ ] Edit YAML in `Recipe YAML`.
- [ ] Click `Validate YAML` and confirm validation passes or reports a useful
  schema error.
- [ ] Click `Save Recipe` and confirm the saved path appears in the recipe field.
- [ ] Click `Dry Run` and confirm `completed=True` appears in the summary or
  metadata.
- [ ] Open the generated run folder.
- [ ] Open the generated plot.
- [ ] Open the generated report.
- [ ] Click `Refresh Runs` in the `Runs` tab.
- [ ] Select an older indexed run.
- [ ] Click `Load Selected` and confirm Summary, Metadata, and Report update.
- [ ] Confirm no hardware output controls are exposed in this GUI phase.

## Development Checklist

- [ ] Keep hardware logic out of CLI argument handling.
- [ ] Keep each measurement family in its own method module.
- [ ] Reuse recipe, runner, instrument, safety, and review layers from the CLI
  and the future GUI.
- [ ] Add or update recipe validation tests for every schema change.
- [ ] Add dry-run support before adding a new hardware path.
- [ ] Ensure errors and interrupts save partial results.
- [ ] Ensure output-off behavior is covered for hardware runners.
- [ ] Update the manual and roadmap whenever a user-facing command changes.
- [ ] Run all tests.
  ```powershell
  python -m pytest
  ```
