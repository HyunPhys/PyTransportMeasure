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
- [x] GUI plot preview renders saved SVG plots in-app.
- [x] GUI schema Recipe Form can generate validated YAML for Drain I-V,
  single-gate, AC lock-in, and pulse recipes.
- [x] GUI plan and dry-run use the current editor YAML draft.
- [x] GUI Drain I-V preflight uses the current editor YAML draft.
- [x] GUI guarded Drain I-V hardware run uses confirmation and preflight gating.
- [x] Run feedback bundles can package lab-laptop results for review.
- [x] Lab-laptop doctor can report environment, VISA resources, and probe state.
- [x] GUI Doctor can run lab-laptop diagnostics from the current editor address.
- [x] GUI Progress tab streams point-by-point dry-run and Drain I-V hardware
  updates.
- [x] GUI Session Log records diagnostics/progress and is included in feedback
  bundles.
- [x] GUI usability pass collapsed dry-run settings, relaxed resize constraints,
  and fixed Session Log scroll behavior.
- [x] GUI Dry-run Model expands into a scrollable settings area instead of
  crushing labels/fields in short windows.
- [x] GUI workspace separates measurement, instruments, and analysis.
- [x] GUI Instruments workspace can refresh VISA resources and test selected
  address communication.
- [x] GUI Recipe Tools show YAML/Form sync status and execution-source guidance.
- [x] GUI Workflow tab tracks the major run-preparation steps and next action.
- [x] GUI plot preview uses a non-stretched points-based plot and live Drain I-V
  plot updates during measurement progress.
- [x] GUI Stop Run requests cooperative Drain I-V interruption with partial
  artifacts and output-off cleanup.
- [x] Lab context metadata tracks cooldown, contact geometry, contact notes, and
  lab notebook reference in recipes/reports.
- [x] GUI Analysis can filter indexed runs by sample, device, cooldown, tag,
  method, and status.
- [x] GUI Analysis can scan selected run folders, sort Runs columns, and
  highlight the currently loaded row.
- [x] GUI Recipe Overview summarizes the current YAML by method, experiment,
  instrument, sweep/pulse/lock-in, output, and checks.
- [x] GUI Recipe Form is generated from the current method recipe schema rather
  than a Drain I-V-only form.
- [x] GUI Schemes workspace can create, validate, plan, and save scheme YAML.
- [x] GUI Schemes workspace can set common Drain I-V step overrides without
  copying the base recipe file.
- [x] GUI Schemes workspace can dry-run supported schemes and show the saved
  scheme result/report.
- [x] GUI Schemes workspace can browse and reload saved scheme summaries from a
  selected source folder.
- [x] GUI Schemes workspace can compare selected saved schemes by per-step run
  statistics.
- [x] GUI Schemes workspace can preview saved scheme overlays from point data
  without embedding stretched SVG artifacts.
- [x] GUI Schemes workspace can filter saved schemes and export comparison rows
  as CSV.
- [x] GUI remembers run/scheme source folders in a small GUI state file.
- [ ] 4-probe / remote sense is documented as TODO, not implemented.
- [ ] Single-gate, AC/lock-in, pulse, and 4-probe GUI hardware runs are future
  milestones.

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
- [ ] Run the lab doctor when working on the lab laptop.
  ```powershell
  ptm doctor --address "GPIB0::2::INSTR"
  ```
- [ ] When using the GUI, confirm the Session Log tab is updating before a
  hardware run.
- [ ] Confirm the GUI window can be resized comfortably on the current display.

## New Drain I-V Recipe

- [ ] Start from a known-good recipe.
  ```powershell
  ptm new-recipe configs/recipes/my_device_iv.yaml --mode linear_one_way --measurement-name my_device_iv --sample-id sample001 --device-id devA
  ```
- [ ] Edit `measurement_name`, `experiment`, `instrument.address`,
  `instrument.terminal`, sweep range, compliance, and output directory.
- [ ] Fill `experiment.cooldown_id`, `experiment.contact_geometry`,
  `experiment.contact_notes`, and `experiment.lab_notebook_ref` when available.
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
- [ ] If reporting a lab-laptop issue, create a feedback bundle with diagnostic
  context.
  ```powershell
  ptm feedback-bundle data\raw\<run_folder> --extra-file doctor.json
  ```
- [ ] Confirm output is off after normal completion, error, or interrupt.
- [ ] If testing GUI `Stop Run` on hardware, use the resistor setup first and
  confirm output is off after the interrupted run.

## GUI Lab Feedback

- [ ] Start the GUI.
  ```powershell
  ptm-gui
  ```
- [ ] Confirm `Session Log` shows `GUI session started`.
- [ ] Confirm `Dry-run Model` starts collapsed and can be opened when fake
  settings need editing.
- [ ] Confirm expanded `Dry-run Model` fields remain readable and scrollable in
  a short window.
- [ ] Confirm workspace tabs are `Measurement`, `Instruments`, and `Analysis`.
- [ ] Open `Measurement > Workflow` and confirm the major steps are listed.
- [ ] Click `Check YAML`, `Refresh Instruments`, `Test Selected Address`,
  `Plan`, and a dry-run; confirm each successful step changes to `[x]`.
- [ ] Edit YAML or the form and confirm recipe-dependent workflow steps reset.
- [ ] Fill `Cooldown`, `Contact geometry`, `Contact notes`, and `Notebook ref`;
  click `Form -> YAML` and confirm they appear under `experiment`.
- [ ] Start a multi-point Drain I-V dry-run, click `Stop Run`, and confirm
  metadata records `completed=false` and `interrupted=true`.
- [ ] Run `Doctor`, `Preflight`, or `Dry Run`.
- [ ] Confirm `Doctor` lives under `Instruments`.
- [ ] Confirm prior runs, plot preview, reports, and feedback bundle controls
  live under `Analysis`.
- [ ] In `Analysis`, filter runs by sample/device/cooldown/status and confirm
  `Refresh Runs` updates the table.
- [ ] Use `Source Folder` to select a different run parent folder, then confirm
  `Refresh Runs` scans that location.
- [ ] Click Runs table headers and confirm rows sort.
- [ ] Load a row and confirm it is highlighted in light blue.
- [ ] Click `Clear Filters` and confirm the recent run list returns.
- [ ] Confirm `Measurement > Live Plot` updates during a dry-run.
- [ ] Confirm the Session Log tab accumulates the same major events and progress
  lines.
- [ ] Keep Session Log at the bottom and confirm new lines stay visible.
- [ ] Scroll Session Log upward and confirm new lines do not force it back to
  the top or bottom.
- [ ] After a saved run is loaded or completed, press `Feedback Bundle`.
- [ ] Confirm the ZIP contains the run artifacts and `extras/<gui_session_log>.log`.

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
- [ ] Run the two-SMU preflight and confirm both instruments pass.
  ```powershell
  ptm single-gate-preflight configs/recipes/single_gate_hardware_smoke.yaml
  ```
  Confirm `Drain/gate addresses distinct: True`, both `address found: True`,
  and `Single-gate preflight OK: True`.
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
- [ ] Probe SR860 communication without changing measurement settings.
  ```powershell
  ptm identify --instrument srs_sr860 --address "GPIB0::4::INSTR"
  ptm probe --instrument srs_sr860 --address "GPIB0::4::INSTR"
  ptm doctor --instrument srs_sr860 --address "GPIB0::4::INSTR"
  ```
- [ ] Confirm the probe reports an SR860 identity, `error_status: 0`, and a
  decimal `lia_status`.
- [ ] Confirm the active method recipe owns the lock-in block.
- [ ] Confirm the timing mode is explicit, starting with `after_dc_settle`.
- [ ] Confirm every Keithley source block has the intended `nplc` value.
- [ ] Run the two-instrument AC preflight.
  ```powershell
  ptm ac-lockin-preflight configs/recipes/ac_lockin_dry_run.yaml
  ```
- [ ] Confirm `Source/lock-in addresses distinct: True`, both addresses are
  found, and `AC lock-in preflight OK: True`.
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
- [ ] Select `Drain I-V`, open `Recipe Form`, edit one non-hardware field, and
  click `Form -> YAML`.
- [ ] Select `Pulse measurement`, open `Recipe Form`, edit `pulse.count`, and
  click `Form -> YAML`.
- [ ] Select `AC lock-in sweep` and confirm lock-in fields appear in
  `Recipe Form`.
- [ ] Select `Single-gate sweep` and confirm drain/gate instrument fields appear
  in `Recipe Form`.
- [ ] Confirm the Recipe Tools status says form edits are not used until
  `Form -> YAML`.
- [ ] Open `Recipe YAML` and confirm the generated YAML reflects the form value.
- [ ] Edit `Recipe YAML` directly and confirm the status says YAML remains the
  execution source.
- [ ] Open `Recipe Overview` and confirm the current method, instrument block,
  sweep or pulse block, output, and checks match the YAML.
- [ ] Click `Plan` before saving and confirm the plan reflects the unsaved edit.
- [ ] Edit YAML in `Recipe YAML`.
- [ ] Click `Dry Run` before saving and confirm the result uses the unsaved edit.
- [ ] Open `Progress` and confirm dry-run point lines appear.
- [ ] Open `Instruments`, click `Refresh Instruments`, and confirm detected
  VISA resources appear.
- [ ] Select an address and click `Test Selected Address`.
- [ ] Click `Full Doctor` and confirm the status view updates.
- [ ] Click `Preflight` for Drain I-V and confirm the `Preflight` tab updates.
- [ ] Click `Check YAML` and confirm validation passes or reports a useful
  schema error.
- [ ] Click `Save YAML As` and confirm the saved path appears in the recipe field.
- [ ] Click `Dry Run` and confirm `completed=True` appears in the summary or
  metadata.
- [ ] Open the generated run folder.
- [ ] Open the generated plot.
- [ ] Open the generated report.
- [ ] Open `Analysis` and click `Refresh Runs` in the `Runs` subtab.
- [ ] Select an older indexed run.
- [ ] Click `Load Selected` and confirm Summary, Metadata, and Report update.
- [ ] Open `Analysis > Plot` and confirm the points-based plot appears in the app.
- [ ] Confirm `Hardware Run` appears only for Drain I-V in this GUI phase.

## GUI Scheme Builder Checklist

- [ ] Launch `ptm-gui`.
- [ ] Open `Schemes`.
- [ ] Confirm the default scheme has at least two rows.
- [ ] Edit the scheme name.
- [ ] Edit a step label.
- [ ] For a `drain_iv` row, set `Suffix`, `Start V`, `Stop V`, and `Points`.
- [ ] Click `Form -> Scheme YAML` and confirm the YAML updates.
- [ ] Confirm the generated scheme YAML contains `overrides` for the edited
  `drain_iv` row.
- [ ] Click `Check Scheme` and confirm validation passes.
- [ ] Click `Scheme Plan` and confirm the expanded plan and `Overrides` section
  appear.
- [ ] Set `Dry-run Model` fake resistance to match the recipe quality checks
  when using resistor-smoke-test recipes.
- [ ] Click `Dry Run Scheme`.
- [ ] Confirm `Result` shows the scheme summary path and scheme quality.
- [ ] Confirm `Report` shows a Markdown scheme report.
- [ ] Confirm `Scheme Folder` and `Scheme Report` become enabled.
- [ ] Confirm the saved scheme folder contains `scheme_summary.json`,
  `scheme_report.md`, `scheme_runs.csv`, `scheme_points.csv`,
  `scheme_stats.csv`, and, when plottable, `scheme_overlay.svg`.
- [ ] Click `Refresh Saved`.
- [ ] Confirm the saved scheme appears in `Saved`.
- [ ] Set saved filters by name, completion, QC, or dry-run state and confirm
  `Refresh Saved` narrows the table.
- [ ] Change the saved scheme source folder, close/reopen the GUI, and confirm
  the field is remembered.
- [ ] Type a scheme-name filter and press Enter, then confirm the table refreshes.
- [ ] Select the row and confirm `Load Selected` becomes enabled.
- [ ] Click `Load Selected`.
- [ ] Confirm `Result` and `Report` update to the selected saved scheme.
- [ ] Select one or more rows in `Saved`.
- [ ] Click `Compare Selected`.
- [ ] Confirm `Compare` shows per-scheme/per-step statistics.
- [ ] Click `Export CSV` and confirm the CSV contains the comparison rows.
- [ ] Sort by `Mean R` or `Rel Std %` and confirm the rows reorder.
- [ ] Click `Load Selected` on a scheme with Drain I-V-style runs.
- [ ] Open `Overlay`.
- [ ] Confirm the overlay preview redraws when the window is resized.
- [ ] Use `Source Folder` to select another scheme parent folder and refresh.
- [ ] Change a row to `batch` and set the path to
  `../batches/drain_iv_1k_repeat_linear.yaml`.
- [ ] Click `Form -> Scheme YAML`, then `Scheme YAML -> Form`, and confirm the
  row round-trips.
- [ ] Save the scheme only after validation passes.

## GUI Drain I-V Preflight Checklist

- [ ] Confirm the Keithley is connected and in SCPI command set.
- [ ] Confirm the expected VISA address with `ptm list-resources`.
- [ ] Launch `ptm-gui`.
- [ ] Select `Drain I-V`.
- [ ] Confirm the YAML editor has the intended address and safety preset.
- [ ] Open `Instruments`, click `Refresh Instruments`, select the expected
  address, and click `Test Selected Address`.
- [ ] Confirm `OK: True`.
- [ ] Click `Preflight`.
- [ ] Confirm the `Preflight` tab lists the VISA resources.
- [ ] Confirm `Recipe address found: True`.
- [ ] Confirm the probe identifies the Keithley 2450.
- [ ] Confirm `Preflight OK: True`.
- [ ] Confirm `Hardware Run` shows a confirmation dialog before any output can
  be enabled.

## GUI Drain I-V Hardware Run Checklist

- [ ] Start with a 1 kOhm resistor or another safe test load.
- [ ] Confirm the Keithley is connected and in SCPI command set.
- [ ] Confirm the expected VISA address with `ptm list-resources`.
- [ ] Launch `ptm-gui`.
- [ ] Select `Drain I-V`.
- [ ] Confirm the YAML editor has the intended address, terminal, sweep,
  compliance, safety preset, and output directory.
- [ ] Click `Plan` and inspect the sweep points.
- [ ] Open `Instruments`, click `Refresh Instruments`, select the expected
  address, and click `Test Selected Address`.
- [ ] Confirm `Address found: True`.
- [ ] Click `Preflight` and confirm `Preflight OK: True`.
- [ ] Click `Hardware Run`.
- [ ] Read the confirmation dialog and confirm every field.
- [ ] Click `No` once to confirm cancellation works.
- [ ] Click `Hardware Run` again and click `Yes` only when ready.
- [ ] Open `Progress` and confirm point lines appear during the run.
- [ ] Confirm Keithley output turns off after the run.
- [ ] Open `Analysis` and confirm Summary, Metadata, Plot, and Report update.
- [ ] Confirm `completed=True` for a normal run.
- [ ] Click `Feedback Bundle` and confirm a ZIP is created under
  `data/feedback`.

## Lab Laptop Feedback Checklist

- [ ] Pull the latest branch on the lab laptop.
- [ ] Run a doctor report before hardware debugging.
  ```powershell
  ptm doctor --address "GPIB0::2::INSTR" --json --output doctor.json
  ```
- [ ] Run the intended dry-run or hardware measurement.
- [ ] Record the exact command or GUI workflow used.
- [ ] Create a feedback bundle.
  ```powershell
  ptm feedback-bundle data\raw\<run_folder>
  ```
- [ ] Confirm the command prints `Feedback bundle ZIP: ...`.
- [ ] Send the ZIP path/name along with a short description of what happened.
- [ ] If the bundle is large, rerun with `--no-points`, `--no-plots`, or
  `--no-reports` as appropriate.

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
