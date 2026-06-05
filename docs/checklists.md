# PyTransportMeasure Checklists

This document is the practical checklist for running and extending
PyTransportMeasure. Use the smallest checklist that matches the task.

## Current Phase Snapshot

- [x] Keithley 2450 Drain I-V hardware smoke test is working.
- [x] Drain I-V summary, plot, report, and quality checks are available.
- [x] Batch, scheme, and campaign review flows are available.
- [x] Single-gate workflow is dry-run verified.
- [x] Dual-gate workflow is dry-run verified and hardware-blocked.
- [x] Dual-gate lock-in workflow is dry-run verified and preflight-gated.
- [x] SR860 / AC lock-in workflow is dry-run verified.
- [x] Two-terminal AC lock-in hardware smoke path is available after preflight.
- [ ] Single-gate two-SMU hardware smoke test still needs lab confirmation.
- [ ] Dual-gate hardware topology still needs design before output is enabled.
- [x] Dual-gate lock-in hardware preflight checks two gate Keithleys and SR860.
- [x] Dual-gate lock-in limited active sweep records recovery metadata for
  completion, interruption, exception, and safety-stop review.
- [x] Keithley/SR860 AC lock-in preflight checks both resources before hardware
  output is enabled.
- [x] AC and dual-gate lock-in preflight compare declared SR860 expected
  settings against read-only SR860 setting readback.
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
- [x] Recipes now distinguish sample contact metadata from explicit
  `measurement_geometry`.
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
- [ ] For Keithley-only DC runs, confirm `measurement_geometry.method` is
  `two_terminal`.
- [ ] For SR860 four-terminal lock-in runs, confirm `measurement_geometry.method:
  four_terminal`, `terminal_count: 4`, `lockin.input_mode: voltage`, and
  `lockin.voltage_input: a-b`.
- [ ] Set Keithley `instrument.voltage_range_v`, `instrument.current_range_a`,
  and `instrument.nplc` intentionally. Hardware runs are blocked when any active
  Keithley 2450 block is missing these values.
- [ ] Treat `nplc` as a measurement condition, not a UI/default detail: larger
  values average current longer and slow the sweep.
- [ ] If using Keithley source delay, set `instrument.source_delay_s` and
  remember it is in addition to Python-side sweep delay.
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

## Dual-Gate Dry-Run Checklist

Use this for Hall bar graphene workflow development before any dual-gate
hardware output is enabled.

- [ ] Preview the dual-gate plan.
  ```powershell
  ptm dual-gate-plan configs/recipes/dual_gate_dry_run.yaml
  ```
- [ ] Confirm the plan shows separate drain, gate1, and gate2 instrument blocks.
- [ ] Confirm every Keithley block has the intended `nplc` value.
- [ ] If any active Keithley block is missing `nplc`, confirm the hardware
  command exits before output with a measurement-parameter error.
- [ ] Confirm `Total points` equals `gate1 points x gate2 points x drain points`.
- [ ] Run the dry-run artifact path.
  ```powershell
  ptm dual-gate configs/recipes/dual_gate_dry_run.yaml --dry-run --summary --plot --report --gate-stats --fake-noise-std-a 0
  ```
- [ ] Confirm `points.csv` contains `gate1_voltage_v`, `gate2_voltage_v`,
  `drain_voltage_v`, `drain_current_a`, `gate1_current_a`, and
  `gate2_current_a`.
- [ ] Confirm `dual_gate_heatmap.svg`, `dual_gate_stats.csv`, and
  `dual_gate_report.md` are written.
- [ ] Confirm generic saved-run commands work.
  ```powershell
  ptm summarize data\raw\<dual_gate_run_folder>
  ptm plot data\raw\<dual_gate_run_folder>
  ptm report data\raw\<dual_gate_run_folder>
  ```
- [ ] Confirm non-dry-run hardware dual-gate is blocked.
  ```powershell
  ptm dual-gate configs/recipes/dual_gate_dry_run.yaml
  ```

## Dual-Gate Lock-In Dry-Run Checklist

Use this for the likely two-Keithley-plus-SR860 Hall bar graphene path. A tiny
guarded active sweep is available after smoke tests; broader hardware scans
remain point-guarded.

- [ ] Preview the lock-in dual-gate plan.
  ```powershell
  ptm dual-gate-lockin-plan configs/recipes/dual_gate_lockin_dry_run.yaml
  ```
- [ ] Confirm the plan shows gate1 Keithley, gate2 Keithley, SR860 address,
  NPLC values, source-delay values when set, lock-in channels, and
  `after_dc_settle` timing.
- [ ] Confirm the plan shows the Hall-bar topology:
  gate roles, source/drain contacts, lock-in input contacts, excitation source,
  excitation contacts, excitation amplitude, and current-bias resistor if used.
- [ ] Confirm the plan shows the nominal source-drain AC current when
  `excitation_amplitude_v` and `current_bias_resistor_ohm` are declared.
- [ ] Confirm the plan `Scan readiness` block shows the total gate-grid point
  count, gate voltage steps, minimum programmed settle time, and default point
  guard status.
- [ ] Run the three-instrument preflight on the lab laptop.
  ```powershell
  ptm dual-gate-lockin-preflight configs/recipes/dual_gate_lockin_dry_run.yaml
  ```
- [ ] Confirm `Gate1/gate2/lock-in addresses distinct: True`, all three
  addresses are found, both gate probes identify Keithley 2450 instruments, the
  lock-in probe identifies SR860, and `Dual-gate lock-in preflight OK: True`.
- [ ] Confirm the preflight `Topology` section matches the actual device wiring
  before connecting a real graphene Hall bar.
- [ ] Confirm the preflight `Scan readiness` section matches the intended scan
  size before raising `--max-hardware-points`.
- [ ] Confirm the preflight `Lock-in setting check` shows every declared SR860
  expected setting and ends with `all expected settings match: True`.
- [ ] If `Dual-gate lock-in preflight OK: False` is caused by a lock-in setting
  mismatch, fix the SR860 front-panel setting or recipe expectation before
  enabling any gate output.
- [ ] Run the readout smoke after preflight. This reads SR860 only and does not
  enable gate outputs.
  ```powershell
  ptm dual-gate-lockin-smoke configs/recipes/dual_gate_lockin_dry_run.yaml --samples 5 --interval-s 0.2 --progress
  ```
- [ ] Confirm `lockin_smoke.csv` and `metadata.json` are written.
- [ ] Confirm metadata says `gate_outputs_enabled: false`.
- [ ] Confirm SR860 X/Y/R/theta values are reasonable for the current
  front-panel settings and wiring.
- [ ] Run the active-gate smoke only after readout smoke looks reasonable.
  Start with a small gate voltage pair.
  ```powershell
  ptm dual-gate-lockin-active-smoke configs/recipes/dual_gate_lockin_dry_run.yaml --gate1-v 0.01 --gate2-v 0 --samples 3 --settle-s 0.2 --interval-s 0.2 --progress
  ```
- [ ] Confirm the command asks for confirmation before enabling gate outputs
  unless `--yes` is explicitly used.
- [ ] Confirm `active_gate_smoke.csv` includes gate voltage, leakage current,
  compliance flags, and SR860 X/Y/R/theta columns.
- [ ] Confirm metadata has `outputs_off_after_run: true` and
  `gate_outputs_enabled: false` after the run.
- [ ] Confirm metadata has `lockin_settings_readback_available: true`,
  `lockin_settings_readback_matched: true`, and
  `lockin_settings_readback_enforced: true`. If any SR860 setting changed after
  preflight, the runner should stop before gate output turns on.
- [ ] Confirm leakage currents are below the chosen safety/current-compliance
  limits before any active gate sweep work begins.
- [ ] Preview the limited active 2x2 sweep recipe.
  ```powershell
  ptm dual-gate-lockin-plan configs/recipes/dual_gate_lockin_limited_active.yaml
  ```
- [ ] Confirm `Total points: 4`, small gate voltage range, intended NPLC,
  source-delay values when set, and topology before hardware output.
- [ ] Run the limited active sweep only after the active-gate smoke passes.
  ```powershell
  ptm dual-gate-lockin configs/recipes/dual_gate_lockin_limited_active.yaml --allow-active-sweep --max-hardware-points 4 --progress --plot --report --gate-stats
  ```
- [ ] Confirm the command asks for confirmation before enabling gate outputs
  unless `--yes` is explicitly used.
- [ ] Confirm metadata has `outputs_off_after_run: true` and
  `gate_outputs_enabled: false` after the sweep.
- [ ] Confirm metadata has `lockin_settings_readback_matched: true` before
  treating the sweep as an accepted run for scale-up.
- [ ] Confirm metadata has `planned_points`, `points_written`,
  `remaining_points`, `abort_class`, `last_completed_index`,
  `next_point_index`, and `recovery_recommendation`.
- [ ] Confirm metadata has `planned_gate_grid`,
  `planned_gate_grid_signature`, and
  `planned_gate_grid_signature_algorithm: sha256_json_v1`.
- [ ] Confirm the generated `dual_gate_lockin_report.md` contains a `Recovery`
  section.
- [ ] For a normal 2x2 sweep, confirm `abort_class: completed`,
  `planned_points: 4`, `points_written: 4`, and `remaining_points: 0`.
- [ ] Audit the saved limited active sweep before expanding the hardware grid.
  ```powershell
  ptm dual-gate-lockin-audit data\raw\<dual_gate_lockin_run_folder> --write-report
  ```
- [ ] Confirm the audit prints `Dual-gate lock-in acceptance: PASS`.
- [ ] Confirm the audit prints gate1/gate2 leakage maxima and
  leakage/compliance margins.
- [ ] Confirm no `gate*_leakage_margin` warning appears before using this run
  as `--accepted-previous-run` for a larger hardware grid.
- [ ] If any leakage/compliance margin warning appears, repeat a limited run or
  fix the leakage cause before increasing gate range or point count. The CLI
  blocks scale-up checks and raised-point hardware runs in this case.
- [ ] Confirm `dual_gate_lockin_acceptance.md` is written.
- [ ] If the audit fails, review the listed issue before changing gate range,
  point count, NPLC, compliance, or SR860 settings.
- [ ] If a safety stop occurs, confirm `abort_class: safety_stop`,
  `outputs_off_after_run: true`, and do not resume until leakage/compliance
  cause is reviewed.
- [ ] Confirm the broader dry-run recipe is blocked by the point guard in
  hardware mode.
  ```powershell
  ptm dual-gate-lockin configs/recipes/dual_gate_lockin_dry_run.yaml --allow-active-sweep --max-hardware-points 4 --yes
  ```
- [ ] If raising `--max-hardware-points` above the default guard, provide
  `--hardware-approval-note` with the lab reason and
  `--accepted-previous-run data\raw\<accepted_limited_run_folder>`.
  ```powershell
  ptm dual-gate-lockin configs/recipes/dual_gate_lockin_limited_active.yaml --allow-active-sweep --max-hardware-points 25 --hardware-approval-note "2x2 accepted; expanding to 5x5" --accepted-previous-run data\raw\<accepted_limited_run_folder> --progress --plot --report --gate-stats
  ```
- [ ] Confirm the accepted previous run passes strict audit before using it.
  ```powershell
  ptm dual-gate-lockin-audit data\raw\<accepted_limited_run_folder> --write-report
  ```
- [ ] Check the candidate broader recipe without enabling hardware output.
  ```powershell
  ptm dual-gate-lockin-scale-up-check data\raw\<accepted_limited_run_folder> configs/recipes/<candidate_broader_recipe>.yaml
  ```
- [ ] Confirm `dual-gate-lockin-scale-up-check` fails if the accepted previous
  run has a leakage-margin warning; do not bypass this by manually raising
  `--max-hardware-points`.
- [ ] Prefer generating the candidate recipe from the accepted run to avoid
  copying topology/SR860/SMU settings by hand.
  ```powershell
  ptm dual-gate-lockin-scale-up-template data\raw\<accepted_limited_run_folder> configs/recipes/dual_gate_lockin_3x3_candidate.yaml --gate1-start-v -0.1 --gate1-stop-v 0.1 --gate1-points 3 --gate2-start-v -0.1 --gate2-stop-v 0.1 --gate2-points 3 --measurement-name dual_gate_lockin_3x3_candidate
  ```
- [ ] Open the generated `.review.md` file and confirm it contains the
  scale-up check command, preflight command, hardware command template, and
  candidate plan.
- [ ] Confirm the raised hardware run prints
  `Dual-gate lock-in scale-up compatibility: PASS` before preflight/output.
- [ ] Confirm runs with raised hardware point guards save `metadata.json`
  `hardware_guard.default_max_hardware_points`,
  `hardware_guard.requested_max_hardware_points`,
  `hardware_guard.raised_above_default`, and
  `hardware_guard.approval_note`,
  `hardware_guard.accepted_previous_run`, and
  `hardware_guard.accepted_previous_run_audit_passed`,
  `hardware_guard.accepted_previous_run_scale_up_compatible`, and
  `hardware_guard.accepted_previous_run_grid_signature`.
- [ ] Run the dry-run artifact path.
  ```powershell
  ptm dual-gate-lockin configs/recipes/dual_gate_lockin_dry_run.yaml --dry-run --summary --plot --report --gate-stats --fake-noise-std 0
  ```
- [ ] Confirm `points.csv` contains `gate1_voltage_v`, `gate2_voltage_v`,
  `gate1_current_a`, `gate2_current_a`, `lockin_x_v`, `lockin_y_v`,
  `lockin_r_v`, `lockin_theta_deg`, `source_drain_nominal_current_a`,
  `lockin_resistance_ohm`, `lockin_conductance_s`,
  `lockin_sheet_resistance_ohm_per_sq`, and
  `lockin_sheet_conductivity_s_per_sq`. For Vxy recipes, also confirm
  `lockin_hall_resistance_ohm` and `lockin_hall_carrier_density_per_m2`.
- [ ] Confirm `dual_gate_lockin_heatmap.svg`,
  `dual_gate_lockin_stats.csv`, and `dual_gate_lockin_report.md` are written.
- [ ] Confirm `dual_gate_lockin_stats.csv` includes
  `lockin_resistance_mean_ohm`, `lockin_conductance_mean_s`, and, for
  longitudinal Vxx recipes with L/W, `lockin_sheet_resistance_mean_ohm_per_sq`.
- [ ] For Vxy recipes with `magnetic_field_t`, confirm
  `lockin_hall_carrier_density_mean_per_m2` is present and has the expected
  sign convention.
- [ ] Generate a consistent Hall-bar Vxx/Vxy recipe set when preparing a real
  Hall device.
  ```powershell
  ptm dual-gate-lockin-hall-suite-template configs\recipes\<base_dual_gate_lockin_recipe>.yaml configs\recipes\<hall_suite_dir> --measurement-prefix <sample_device> --magnetic-field-t <B_abs_T> --longitudinal-contact Vxx+ --longitudinal-contact Vxx- --hall-contact Vxy+ --hall-contact Vxy- --channel-length-m <L_m> --channel-width-m <W_m>
  ```
- [ ] Confirm the generated suite contains Vxx, `+B` Vxy, `-B` Vxy, optional
  `0B` Vxy recipes, and a review markdown with plan/preflight/hardware/analysis
  command templates.
- [ ] Run the suite consistency check before hardware use.
  ```powershell
  ptm dual-gate-lockin-hall-suite-check configs\recipes\<suite>\<prefix>_vxx.yaml configs\recipes\<suite>\<prefix>_vxy_plus_b.yaml configs\recipes\<suite>\<prefix>_vxy_minus_b.yaml --zero-field-recipe configs\recipes\<suite>\<prefix>_vxy_zero_b.yaml
  ```
- [ ] Confirm it prints `Dual-gate lock-in Hall suite consistency: PASS`.
- [ ] Print the aggregate Hall-suite runbook before hardware use.
  ```powershell
  ptm dual-gate-lockin-hall-suite-plan configs\recipes\<suite>\<prefix>_vxx.yaml configs\recipes\<suite>\<prefix>_vxy_plus_b.yaml configs\recipes\<suite>\<prefix>_vxy_minus_b.yaml --zero-field-recipe configs\recipes\<suite>\<prefix>_vxy_zero_b.yaml
  ptm dual-gate-lockin-hall-suite-chunk-plan configs\recipes\<suite>\<prefix>_vxx.yaml configs\recipes\<suite>\<prefix>_vxy_plus_b.yaml configs\recipes\<suite>\<prefix>_vxy_minus_b.yaml --zero-field-recipe configs\recipes\<suite>\<prefix>_vxy_zero_b.yaml --chunk-size <N>
  ```
- [ ] Confirm the suite plan shows the Vxx/+B/-B/0B measurement order,
  per-recipe plan snapshots, preflight commands, guarded hardware command
  templates, and Hall analysis commands.
- [ ] Confirm the Hall-suite chunk plan shows per-recipe chunk-plan commands,
  stitch commands for Vxx/+B/-B/0B, and Hall analysis commands from stitched
  run folders.
- [ ] If chunk feedback suggests changing NPLC, settle time, or SR860 settings,
  generate a new adjusted Hall suite as a group.
  ```powershell
  ptm dual-gate-lockin-hall-suite-adjust-recipes configs\recipes\<suite>\<prefix>_vxx.yaml configs\recipes\<suite>\<prefix>_vxy_plus_b.yaml configs\recipes\<suite>\<prefix>_vxy_minus_b.yaml configs\recipes\<adjusted_suite> --zero-field-recipe configs\recipes\<suite>\<prefix>_vxy_zero_b.yaml --measurement-prefix <prefix_after_feedback> --gate-nplc <NPLC> --gate-settle-s <seconds> --lockin-sensitivity-index <index> --lockin-time-constant-index <index> --lockin-read-settle-s <seconds> --adjustment-note "<chunk feedback>"
  ```
- [ ] Confirm the command writes adjusted Vxx, `+B` Vxy, `-B` Vxy, optional
  `0B` Vxy recipes, and `<prefix_after_feedback>_adjustment_review.md`.
- [ ] Confirm the adjusted suite check passes.
  ```powershell
  ptm dual-gate-lockin-hall-suite-check configs\recipes\<adjusted_suite>\<prefix_after_feedback>_vxx.yaml configs\recipes\<adjusted_suite>\<prefix_after_feedback>_vxy_plus_b.yaml configs\recipes\<adjusted_suite>\<prefix_after_feedback>_vxy_minus_b.yaml --zero-field-recipe configs\recipes\<adjusted_suite>\<prefix_after_feedback>_vxy_zero_b.yaml
  ```
- [ ] Open the adjustment review and confirm Gate1/Gate2 NPLC, Gate1/Gate2
  settle time, SR860 sensitivity/time constant, and SR860 read-settle settings
  match the lab decision before preflight or output.
- [ ] Create a Hall-suite acquisition package for the lab laptop handoff.
  ```powershell
  ptm dual-gate-lockin-hall-suite-package configs\recipes\<adjusted_suite>\<prefix_after_feedback>_vxx.yaml configs\recipes\<adjusted_suite>\<prefix_after_feedback>_vxy_plus_b.yaml configs\recipes\<adjusted_suite>\<prefix_after_feedback>_vxy_minus_b.yaml data\hall_packages --zero-field-recipe configs\recipes\<adjusted_suite>\<prefix_after_feedback>_vxy_zero_b.yaml --package-name <sample_lab_package> --chunk-size <N> --max-hardware-points <N> --acquisition-note "<lab handoff note>"
  ```
- [ ] Confirm the package folder contains `recipes/`, `keithley_audit/`,
  `acquisition_runbook.md`, `package_manifest.json`, and a `.zip` next to the
  folder.
- [ ] Confirm `acquisition_runbook.md` includes suite-check, suite-plan,
  chunk-plan, Keithley parameter audits, per-recipe preflight, chunk feedback,
  adjustment, stitch, and Hall analysis commands.
- [ ] Confirm `package_manifest.json` contains `keithley_parameter_audits` and
  every copied recipe reports `ok_for_hardware: true`.
- [ ] If preflight logs, chunk feedback summaries, or lab notes already exist,
  rerun the package command with `--chunk-feedback-file`, `--preflight-file`,
  or `--note-file` and confirm those files are copied into the package.
- [ ] After the lab laptop completes Vxx/+B/-B/0B runs, intake the returned run
  folders before Hall analysis.
  ```powershell
  ptm dual-gate-lockin-hall-suite-intake data\hall_packages\<sample_lab_package> data\raw\<vxx_run> data\raw\<plus_B_run> data\raw\<minus_B_run> --zero-field-run-dir data\raw\<zero_B_run>
  ```
- [ ] Confirm intake prints `Hall suite result intake: PASS`.
- [ ] Confirm `result_intake_report.md` and `result_intake.json` are written in
  the package folder.
- [ ] Confirm the report shows each run acceptance as PASS and no
  `recipe_match`, `grid_signature`, `voltage_probe_role`, or magnetic-field
  errors.
- [ ] Continue to Hall antisymmetry, zero-field correction, and mobility
  analysis only after intake PASS.
- [ ] Run suite-level Hall analysis after intake PASS.
  ```powershell
  ptm dual-gate-lockin-hall-suite-analyze data\hall_packages\<sample_lab_package>
  ```
- [ ] Confirm `hall_analysis/antisym/hall_antisym.csv` is written.
- [ ] If a zero-field run was supplied, confirm
  `hall_analysis/zero_corrected/hall_zero_corrected.csv` is written.
- [ ] Confirm `hall_analysis/mobility/hall_mobility.csv` is written.
- [ ] Confirm `hall_analysis/hall_suite_analysis_manifest.json` records the
  intake JSON, run folders, value column, and chosen Hall density source.
- [ ] Review the suite-level Hall analysis before choosing the next gate scan.
  ```powershell
  ptm dual-gate-lockin-hall-suite-review data\hall_packages\<sample_lab_package>\hall_analysis
  ```
- [ ] Confirm `hall_suite_analysis_review.md` summarizes carrier density,
  Hall resistance, sheet conductivity/resistance, and mobility ranges.
- [ ] Confirm `hall_suite_analysis_review.json` has
  `accepted_for_next_scan_decision: true` before using the artifacts for the
  next measurement decision.
- [ ] Review all warnings about density sign changes, field-even offsets,
  zero-field offsets, missing mobility values, or gate-grid mismatches.
- [ ] Confirm the Keithley NPLC values used for the underlying source/gate
  SMUs were intentional; do not compare scans with changed NPLC unless the
  lab deliberately changed the integration-time/noise tradeoff.
- [ ] Generate an advisory next-scan proposal only after the review is accepted.
  ```powershell
  ptm dual-gate-lockin-hall-suite-next-scan-proposal data\hall_packages\<sample_lab_package>\hall_analysis
  ```
- [ ] Confirm `hall_suite_next_scan_proposal.json` has
  `hardware_recipe_written: false`, `accepted_for_recipe_generation: false`,
  and `requires_lab_approval: true`.
- [ ] Confirm the proposal preserves Keithley NPLC, voltage range, current
  range, compliance, settle time, and SR860 settings unless the lab notebook
  explicitly approves a change.
- [ ] Approve the next gate window/spacing in the lab notebook before creating
  adjusted hardware recipes or acquisition packages.
- [ ] Generate approved next-scan recipes only with a lab approval note.
  ```powershell
  ptm dual-gate-lockin-hall-suite-approved-next-scan data\hall_packages\<sample_lab_package>\hall_analysis configs\recipes\<approved_next_suite> --approval-note "<lab notebook approval>" --measurement-prefix <approved_prefix>
  ```
- [ ] Confirm the generated review says the command only applied the approved
  gate grid and preserved Keithley NPLC/range/compliance/source-delay and SR860
  settings by default.
- [ ] Run suite check on the approved recipes before packaging or hardware use.
  ```powershell
  ptm dual-gate-lockin-hall-suite-check configs\recipes\<approved_next_suite>\<prefix>_vxx.yaml configs\recipes\<approved_next_suite>\<prefix>_vxy_plus_b.yaml configs\recipes\<approved_next_suite>\<prefix>_vxy_minus_b.yaml --zero-field-recipe configs\recipes\<approved_next_suite>\<prefix>_vxy_zero_b.yaml
  ```
- [ ] Create an approved next-scan acquisition package for the lab laptop.
  ```powershell
  ptm dual-gate-lockin-hall-suite-approved-next-scan-package configs\recipes\<approved_next_suite>\<prefix>_vxx.yaml configs\recipes\<approved_next_suite>\<prefix>_vxy_plus_b.yaml configs\recipes\<approved_next_suite>\<prefix>_vxy_minus_b.yaml data\hall_packages --zero-field-recipe configs\recipes\<approved_next_suite>\<prefix>_vxy_zero_b.yaml --proposal-json data\hall_packages\<previous_package>\hall_analysis\hall_suite_next_scan_proposal.json --approval-review configs\recipes\<approved_next_suite>\<prefix>_approved_next_scan_review.md --package-name <approved_next_package> --chunk-size <N>
  ```
- [ ] Confirm `package_manifest.json` includes `approved_next_scan`.
- [ ] Confirm `acquisition_runbook.md` includes `Approved Next-Scan Provenance`.
- [ ] Confirm the ZIP includes copied recipes, the proposal JSON, and the
  approval review markdown.
- [ ] Use chunked acquisition from the package runbook, then run result intake
  against this approved package before Hall analysis.
- [ ] Rehearse the approved package locally with fake instruments before lab
  handoff.
  ```powershell
  ptm dual-gate-lockin-hall-suite-approved-next-scan-rehearse data\hall_packages\<approved_next_package>
  ```
- [ ] Confirm `dry_run_rehearsal/rehearsal_summary.json` has `completed: true`.
- [ ] Confirm rehearsal artifacts include fake runs, result intake, Hall
  analysis, analysis review, and a next proposal JSON.
- [ ] Confirm the rehearsal summary carries `approved_next_scan` provenance.
- [ ] Print the read-only Hall workflow status before lab handoff.
  ```powershell
  ptm dual-gate-lockin-hall-suite-status data\hall_packages\<approved_next_package>
  ```
- [ ] Confirm package manifest, runbook, ZIP, copied recipes, approved
  provenance, and dry-run rehearsal show PASS or expected review status.
- [ ] If a dual-gate lock-in run is interrupted, resume into a new run folder.
  ```powershell
  ptm dual-gate-lockin-resume-check configs\recipes\<dual_gate_lockin_recipe>.yaml data\raw\<partial_run_folder>
  ptm dual-gate-lockin configs\recipes\<dual_gate_lockin_recipe>.yaml --allow-active-sweep --resume-from-run data\raw\<partial_run_folder> --max-hardware-points <N> --hardware-approval-note "<lab note>" --accepted-previous-run data\raw\<accepted_run> --yes --progress --plot --report --gate-stats
  ```
- [ ] Confirm resume-check prints `Dual-gate lock-in resume check: PASS` and
  the intended next gate voltages before enabling hardware output.
- [ ] For a deliberately limited checkpoint scan, use
  `--stop-after-new-points <N>` and confirm the run ends with
  `abort_class: checkpoint`, `checkpoint_reached: true`, and outputs off.
- [ ] After each checkpoint chunk, run chunk audit before resuming.
  ```powershell
  ptm dual-gate-lockin-chunk-audit data\raw\<chunk_run_folder>
  ```
- [ ] Confirm it prints `Dual-gate lock-in checkpoint acceptance: PASS` and
  shows acceptable gate leakage/compliance margins.
- [ ] After one or more chunks, summarize chunk feedback.
  ```powershell
  ptm dual-gate-lockin-chunk-feedback data\raw\<chunk_01_run> data\raw\<chunk_02_run> --output docs\<sample>_chunk_feedback.md
  ```
- [ ] Confirm it prints `Dual-gate lock-in chunk feedback: PASS` before keeping
  the same chunk size, NPLC, settle time, and SR860 sensitivity.
- [ ] If feedback indicates noisy signal or marginal settling, create an
  adjusted recipe instead of hand-editing the hardware recipe.
  ```powershell
  ptm dual-gate-lockin-adjust-recipe configs\recipes\<candidate_recipe>.yaml configs\recipes\<adjusted_recipe>.yaml --gate-nplc <NPLC> --gate-settle-s <seconds> --lockin-sensitivity-index <index> --lockin-time-constant-index <index> --lockin-settle-time-constants <N> --adjustment-note "<lab feedback>"
  ```
- [ ] Confirm the generated review markdown shows the intended NPLC, settle
  time, SR860 sensitivity, time constant, and preflight command.
- [ ] Before chunked hardware work, print the chunk runbook.
  ```powershell
  ptm dual-gate-lockin-chunk-plan configs\recipes\<dual_gate_lockin_recipe>.yaml --chunk-size <N> --max-hardware-points <N>
  ```
- [ ] Before the first broader scan, write a broader-scan packet.
  ```powershell
  ptm dual-gate-lockin-broader-scan-packet data\raw\<accepted_run> configs\recipes\<candidate_dual_gate_lockin_recipe>.yaml --chunk-size <N> --max-hardware-points <N> --output docs\<sample>_broader_scan_packet.md
  ```
- [ ] Confirm the packet says `Packet ready for lab execution: yes`.
- [ ] Confirm the packet's measurement-parameter table shows intentional
  Keithley voltage range, current range, NPLC, source delay, gate sweep, and
  compliance values for both gate SMUs.
- [ ] Confirm the packet includes `scale-up-check`, `preflight`, `chunk-plan`,
  chunk acquisition, chunk audit, chunk feedback, stitch, and strict audit
  commands.
- [ ] After all chunks are measured, stitch them into one analysis-ready run.
  ```powershell
  ptm dual-gate-lockin-stitch-chunks data\raw\<chunk_01_run> data\raw\<chunk_02_run> data\raw\<chunk_03_run> --measurement-name <stitched_name> --gate-stats --plot --report
  ```
- [ ] Confirm stitched metadata has `stitched_from_chunks: true`,
  `completed: true`, and contiguous point indices from 0 to `planned_points - 1`.
- [ ] Confirm the resumed metadata records `resume_from_run`,
  `points_copied_from_resume`, `points_measured_this_run`, and
  `resume_next_point_index`.
- [ ] Confirm the original partial run folder is unchanged and the resumed
  `points.csv` contains the copied prefix plus newly measured remaining points.
- [ ] When matched `+B` and `-B` Hall runs are available, run
  `ptm dual-gate-lockin-hall-antisym data\raw\<plus_B_run> data\raw\<minus_B_run>
  --output-dir data\analysis\<hall_antisym_folder>` and confirm
  `hall_antisym.csv` and `hall_antisym_report.md` are written.
- [ ] When a finite-field Hall run and a matching `B=0` Hall run are available,
  run `ptm dual-gate-lockin-hall-zero-correct data\raw\<field_B_run>
  data\raw\<zero_B_run> --output-dir data\analysis\<hall_zero_corrected_folder>`
  and confirm `hall_zero_corrected.csv`,
  `hall_zero_corrected_report.md`, and
  `hall_zero_corrected_metadata.json` are written.
- [ ] Confirm `hall_zero_corrected.csv` contains
  `hall_zero_corrected_resistance_ohm` and
  `hall_carrier_density_per_m2`.
- [ ] After a matching longitudinal Vxx run is available, run
  `ptm dual-gate-lockin-hall-mobility data\analysis\<hall_density_folder>
  data\raw\<longitudinal_Vxx_run> --output-dir data\analysis\<hall_mobility_folder>`
  and confirm `hall_mobility.csv`, `hall_mobility_report.md`, and
  `hall_mobility_metadata.json` are written.
- [ ] Confirm `<hall_density_folder>` may be either the antisymmetry output
  folder or the zero-field-corrected output folder, depending on which Hall
  measurement set is available.
- [ ] Confirm `hall_mobility.csv` contains `hall_carrier_density_per_m2`,
  `hall_source_kind`, `hall_source_resistance_ohm`,
  `longitudinal_sheet_conductivity_s_per_sq`,
  `mobility_signed_m2_per_v_s`, and
  `mobility_magnitude_cm2_per_v_s`.
- [ ] For any hardware run used in the Hall/mobility chain, confirm every active
  Keithley source block declares the intended `voltage_range_v`,
  `current_range_a`, and `nplc` before output is enabled.
- [ ] Confirm `dual_gate_lockin_report.md` lists nominal source-drain current,
  resistance range, conductance range, measurement geometry, lock-in voltage
  contacts, excitation contacts, and sheet resistance range when channel
  geometry is declared.
- [ ] Confirm generic saved-run commands work.
  ```powershell
  ptm summarize data\raw\<dual_gate_lockin_run_folder>
  ptm plot data\raw\<dual_gate_lockin_run_folder>
  ptm report data\raw\<dual_gate_lockin_run_folder>
  ```
- [ ] Confirm non-dry-run hardware dual-gate lock-in is blocked.
  ```powershell
  ptm dual-gate-lockin configs/recipes/dual_gate_lockin_dry_run.yaml
  ```

## Four-Terminal / Remote-Sense Smoke Test

- [ ] Confirm the future recipe explicitly states `measurement_geometry.method:
  four_terminal` and `terminal_count: 4`.
- [ ] For SR860 lock-in voltage readout, confirm `lockin.input_mode: voltage`
  and `lockin.voltage_input: a-b`.
- [ ] For dual-gate Hall-bar lock-in, confirm voltage contacts and excitation
  contacts are distinct and non-overlapping.
- [ ] For Keithley 2450 remote-sense DC work, confirm the future implementation
  explicitly states `remote_4wire`; this path is still blocked.
- [ ] Confirm the plan prints the selected sense mode before hardware access.
- [ ] Use a known resistor or resistor network before a real device.
- [ ] Confirm SCPI mode with `ptm probe`.
- [ ] Confirm front or rear terminal selection; do not mix terminal panels.
- [ ] Connect FORCE HI/LO and SENSE HI/LO correctly.
- [ ] Confirm sense leads are attached close to the DUT.
- [ ] Compare against a 2-wire baseline.
- [ ] Confirm output-off behavior after completion, stop, and interrupt.

## SR860 / Lock-In Smoke Test

Use this checklist for the current conservative two-terminal AC lock-in smoke
path. It uses Keithley source bias plus SR860 X/Y/R/theta readout.

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
- [ ] Confirm every Keithley source block has the intended `voltage_range_v`,
  `current_range_a`, and `nplc` values.
- [ ] Confirm AC lock-in hardware smoke is blocked if
  `source_instrument.voltage_range_v`, `source_instrument.current_range_a`, or
  `source_instrument.nplc` is missing.
- [ ] Confirm SR860 expected settings are explicit when they matter:
  `reference_source`, `reference_frequency_hz`, `sine_output_amplitude_v`,
  `input_mode`, `voltage_input`, `input_coupling`, `input_grounding`,
  `voltage_input_range_v`, `sensitivity_index`, `time_constant_index`,
  `settle_time_constants` or `read_settle_s`, `filter_slope_db_per_oct`, and
  `synchronous_filter`.
- [ ] Confirm the plan output prints the expected Keithley NPLC, Keithley source
  delay when set, SR860 settings, SR860 time constant, and `Lock-in read
  settle` before any hardware run.
- [ ] Confirm `ptm probe --instrument srs_sr860` reports `setting_*` fields for
  SR860 reference, excitation, input, range, sensitivity, filter, and sync
  settings.
- [ ] Confirm the physical SR860 front-panel settings match the recipe. Current
  hardware code reads and verifies settings but does not configure the SR860.
- [ ] Run the two-instrument AC preflight.
  ```powershell
  ptm ac-lockin-preflight configs/recipes/ac_lockin_dry_run.yaml
  ```
- [ ] Confirm `Source/lock-in addresses distinct: True`, both addresses are
  found, `all expected settings match: True`, and
  `AC lock-in preflight OK: True`.
- [ ] Dry-run with `FakeLockIn`.
  ```powershell
  ptm ac-lockin configs/recipes/ac_lockin_dry_run.yaml --dry-run --summary --plot --report --fake-resistance-ohm 1000000 --fake-lockin-r-v 0.000002 --fake-lockin-phase-deg 30 --fake-noise-std 0
  ```
- [ ] For hardware smoke, edit `configs/recipes/ac_lockin_hardware_smoke.yaml`
  with the real Keithley source and SR860 addresses.
- [ ] Preview and preflight the hardware smoke recipe.
  ```powershell
  ptm ac-lockin-plan configs/recipes/ac_lockin_hardware_smoke.yaml
  ptm ac-lockin-preflight configs/recipes/ac_lockin_hardware_smoke.yaml
  ```
- [ ] Confirm the hardware smoke plan prints `Lock-in read settle: 0.3 s` when
  using `time_constant_index: 10` and `settle_time_constants: 3.0`.
- [ ] Run the first hardware smoke test without `--yes`.
  ```powershell
  ptm ac-lockin configs/recipes/ac_lockin_hardware_smoke.yaml --progress --summary --plot --report
  ```
- [ ] Verify `lockin_x_v`, `lockin_y_v`,
  `lockin_r_v`, and `lockin_theta_deg` columns.
- [ ] Confirm lock-in readout appears in summary/report artifacts.
- [ ] Open `metadata.json` and confirm `lockin_settings_readback_available:
  true`, `lockin_settings_readback_matched: true`, and
  `lockin_settings_readback_enforced: true`.
- [ ] Confirm source instruments still turn off after completion, stop, and
  interrupt.
- [ ] Open `metadata.json` and confirm the relevant `configured_*_smu`
  snapshot records the intended compliance, range, terminal, NPLC, and source
  delay values.
- [ ] Confirm the matching `configured_*_smu_readback` exists. If any value is
  `ERROR ...`, keep the run artifacts but review the corresponding Keithley
  query before trusting broader scans.
- [ ] Confirm `configured_*_smu_readback_check.matched` is `true` for every
  active Keithley block. If the run stopped with
  `*_smu_config_readback`, output should not have enabled.
- [ ] Confirm every active role in `output_state` has `enabled: false` and
  `off_after_run: true`. If `output_off_error` is present, treat the run as a
  hardware cleanup issue before repeating the scan.
- [ ] Confirm every active role has `zero_before_off_succeeded: true` with
  `zero_before_off_target_v: 0.0`. If not, review the saved error before
  repeating a gate scan.
- [ ] For interrupted or partial scans, record
  `last_commanded_voltage_before_zero_v` for each active gate/source role before
  deciding whether to repeat or expand the scan.

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
