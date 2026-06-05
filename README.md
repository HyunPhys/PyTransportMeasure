# PyTransportMeasure

PyTransportMeasure is a hardware-first transport measurement tool. Phase 0 is a
small, verified Keithley 2450 Drain I-V core.

Current verified setup and supported workflows:

- Keithley 2450 over VISA/GPIB at `GPIB0::2::INSTR`
- Lab-laptop diagnostics with `ptm doctor`
- SCPI command set
- Front terminals selected in the smoke-test recipe
- 1 kOhm resistor smoke test
- Linear one-way Drain I-V sweep
- Forward/backward and multi-segment Drain I-V recipes
- Batch/session YAML for running multiple recipes in sequence
- Measurement scheme YAML for composing recipes and batches
- Single-gate sweep dry-run core for two-SMU gate/drain workflows
- AC / lock-in dry-run core with fake SR860-style readings
- Pulse-measurement dry-run core with explicit pulse safety limits
- PySide6 GUI foundation for plan preview, YAML recipe validation, dry-run
  artifacts, indexed run browsing, in-app plot preview, Drain I-V form recipe
  building, editor-backed dry-runs, lab doctor, Drain I-V preflight, guarded
  Drain I-V hardware runs, progress streaming, feedback bundles, and report
  review, with GUI session logs included in feedback bundles and usability
  fixes for collapsed dry-run settings, window resizing, log scrolling,
  workspace-separated instruments/analysis views, instrument refresh and
  communication tests, YAML/Form sync status, and live I-V plotting
  plus a method-aware Recipe Overview tab, schema-driven Recipe Form, and GUI
  Scheme Builder with Drain I-V step overrides, scheme dry-runs, and saved
  scheme browsing/comparison
- Extensibility roadmap for later 4-probe hardware, SR860 hardware acquisition,
  pulse hardware, and GUI work
- YAML recipe input
- Measurement plan preview before hardware access
- Recipe-defined quality checks with PASS/FAIL reporting
- CSV points + JSON metadata output
- Recipe and safety snapshots saved with each run
- Summary and SVG plot generation
- Dry-run mode with simulated Ohmic data
- Preflight-gated hardware runs with an explicit confirmation prompt
- Partial save on safety stop or user interrupt
- Experiment metadata saved from YAML recipes

Current non-user-facing foundations:

- 4-probe / remote-sense design is documented but intentionally deferred.
- Pulse hardware output is intentionally blocked until a separate smoke-test
  phase reviews the Keithley pulse command path.
- GUI guarded Drain I-V hardware runs are available; other GUI hardware methods
  remain future milestones.

## Quick Start

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[test]"
python -m pytest
ptm run configs/recipes/drain_iv.yaml --dry-run
```

GUI:

```powershell
pip install -e ".[gui,test]"
ptm-gui
```

## Documentation

- Program manual: [docs/manual.md](docs/manual.md)
- Measurement and development checklists: [docs/checklists.md](docs/checklists.md)
- Development roadmap: [docs/roadmap.md](docs/roadmap.md)
- Keithley 2450 SCPI notes: [docs/keithley_2450_scpi_notes.md](docs/keithley_2450_scpi_notes.md)
- Future method extensibility notes: [docs/phase16_method_extensibility_roadmap.md](docs/phase16_method_extensibility_roadmap.md)
- Method registry notes: [docs/phase17_method_registry.md](docs/phase17_method_registry.md)
- Method registry planning notes: [docs/phase18_method_registry_planning.md](docs/phase18_method_registry_planning.md)
- Single-gate hardware smoke preparation: [docs/phase19_single_gate_hardware_smoke_prep.md](docs/phase19_single_gate_hardware_smoke_prep.md)
- 4-probe remote-sense design spike: [docs/phase20_4probe_remote_sense_design.md](docs/phase20_4probe_remote_sense_design.md)
- SR860 / lock-in foundation: [docs/phase21_lockin_foundation.md](docs/phase21_lockin_foundation.md)
- AC / lock-in recipe skeleton: [docs/phase22_ac_lockin_recipe_skeleton.md](docs/phase22_ac_lockin_recipe_skeleton.md)
- Pulse measurement foundation: [docs/phase23_pulse_foundation.md](docs/phase23_pulse_foundation.md)
- PySide6 GUI foundation: [docs/phase24_gui_foundation.md](docs/phase24_gui_foundation.md)
- GUI recipe builder foundation: [docs/phase25_gui_recipe_builder.md](docs/phase25_gui_recipe_builder.md)
- GUI run browser: [docs/phase26_gui_run_browser.md](docs/phase26_gui_run_browser.md)
- GUI plot preview: [docs/phase27_gui_plot_preview.md](docs/phase27_gui_plot_preview.md)
- GUI Drain I-V form builder: [docs/phase28_gui_drain_iv_form_builder.md](docs/phase28_gui_drain_iv_form_builder.md)
- GUI editor-backed runs: [docs/phase29_gui_editor_backed_runs.md](docs/phase29_gui_editor_backed_runs.md)
- GUI Drain I-V preflight: [docs/phase30_gui_preflight.md](docs/phase30_gui_preflight.md)
- GUI guarded hardware run: [docs/phase31_gui_guarded_hardware_run.md](docs/phase31_gui_guarded_hardware_run.md)
- Run feedback bundles: [docs/phase32_feedback_bundle.md](docs/phase32_feedback_bundle.md)
- Lab-laptop doctor: [docs/phase33_lab_doctor.md](docs/phase33_lab_doctor.md)
- GUI lab doctor: [docs/phase34_gui_doctor.md](docs/phase34_gui_doctor.md)
- GUI progress stream: [docs/phase35_gui_progress_stream.md](docs/phase35_gui_progress_stream.md)
- GUI session log: [docs/phase36_gui_session_log.md](docs/phase36_gui_session_log.md)
- GUI usability pass: [docs/phase37_gui_usability_pass.md](docs/phase37_gui_usability_pass.md)
- GUI workspace reorganization and live plot: [docs/phase38_gui_workspace_reorg_and_live_plot.md](docs/phase38_gui_workspace_reorg_and_live_plot.md)
- GUI instrument refresh and communication test: [docs/phase39_gui_instrument_refresh.md](docs/phase39_gui_instrument_refresh.md)
- GUI recipe sync status: [docs/phase40_gui_recipe_sync_status.md](docs/phase40_gui_recipe_sync_status.md)
- GUI workflow guide: [docs/phase41_gui_workflow_guide.md](docs/phase41_gui_workflow_guide.md)
- GUI dry-run model scroll: [docs/phase42_gui_dry_run_model_scroll.md](docs/phase42_gui_dry_run_model_scroll.md)
- GUI cooperative stop: [docs/phase43_gui_cooperative_stop.md](docs/phase43_gui_cooperative_stop.md)
- Lab context metadata: [docs/phase44_lab_context_metadata.md](docs/phase44_lab_context_metadata.md)
- GUI run filters: [docs/phase45_gui_run_filters.md](docs/phase45_gui_run_filters.md)
- GUI Analysis source folder and sorting: [docs/phase46_gui_analysis_source_and_sort.md](docs/phase46_gui_analysis_source_and_sort.md)
- GUI Recipe Overview: [docs/phase47_gui_recipe_overview.md](docs/phase47_gui_recipe_overview.md)
- GUI schema recipe builder: [docs/phase48_gui_schema_recipe_builder.md](docs/phase48_gui_schema_recipe_builder.md)
- GUI Scheme Builder: [docs/phase49_gui_scheme_builder.md](docs/phase49_gui_scheme_builder.md)
- GUI Scheme Drain I-V overrides: [docs/phase50_gui_scheme_drain_iv_overrides.md](docs/phase50_gui_scheme_drain_iv_overrides.md)
- GUI Scheme dry-run: [docs/phase51_gui_scheme_dry_run.md](docs/phase51_gui_scheme_dry_run.md)
- GUI saved scheme browser: [docs/phase52_gui_saved_scheme_browser.md](docs/phase52_gui_saved_scheme_browser.md)
- GUI scheme comparison: [docs/phase53_gui_scheme_comparison.md](docs/phase53_gui_scheme_comparison.md)

## Hardware Smoke Test

Use a 1 kOhm resistor before connecting a real device.

```powershell
ptm list-resources
ptm probe --instrument keithley_2450 --address "GPIB0::2::INSTR"
ptm validate configs/recipes/drain_iv_1k_resistor.yaml
ptm plan configs/recipes/drain_iv_1k_resistor.yaml
ptm preflight configs/recipes/drain_iv_1k_resistor.yaml
ptm new-recipe configs/recipes/my_device_iv.yaml --mode forward_backward --measurement-name my_device_iv --sample-id sample001 --device-id devA
ptm new-batch configs/batches/my_repeat.yaml --kind repeat --name my_repeat --recipe configs/recipes/my_device_iv.yaml --repeat 3 --interval-s 1.0
ptm new-scheme configs/schemes/my_scheme.yaml --kind recipe_and_batch --name my_scheme --recipe configs/recipes/my_device_iv.yaml --batch configs/batches/my_repeat.yaml
ptm run configs/recipes/drain_iv_1k_resistor.yaml --progress --summary --plot --report
ptm run configs/recipes/drain_iv_1k_resistor.yaml --progress --summary --plot --report --yes
ptm single-gate-plan configs/recipes/single_gate_dry_run.yaml
ptm single-gate configs/recipes/single_gate_dry_run.yaml --dry-run --progress --fake-channel-resistance-ohm 1000000 --fake-noise-std-a 0
ptm single-gate configs/recipes/single_gate_dry_run.yaml --dry-run --summary --plot --report --gate-stats --fake-channel-resistance-ohm 1000000 --fake-noise-std-a 0
ptm single-gate-plan configs/recipes/single_gate_hardware_smoke.yaml
ptm single-gate configs/recipes/single_gate_hardware_smoke.yaml --dry-run --summary --plot --report --gate-stats --fake-channel-resistance-ohm 1000000 --fake-gate-leak-resistance-ohm 1000000000 --fake-noise-std-a 0
ptm ac-lockin-plan configs/recipes/ac_lockin_dry_run.yaml
ptm ac-lockin configs/recipes/ac_lockin_dry_run.yaml --dry-run --summary --plot --report --fake-resistance-ohm 1000000 --fake-lockin-r-v 0.000002 --fake-lockin-phase-deg 30 --fake-noise-std 0
ptm pulse-plan configs/recipes/pulse_dry_run.yaml
ptm pulse configs/recipes/pulse_dry_run.yaml --dry-run --summary --plot --report --progress --fake-resistance-ohm 1000000 --fake-noise-std-a 0
ptm single-gate-summary data\raw\<single_gate_run_folder>
ptm single-gate-plot data\raw\<single_gate_run_folder>
ptm single-gate-stats data\raw\<single_gate_run_folder>
ptm single-gate-report data\raw\<single_gate_run_folder>
ptm list-runs --measurement-type single_gate_sweep
ptm check-run data\raw\<run_folder>
ptm batch configs/batches/drain_iv_1k_smoke_suite.yaml --dry-run --summary --plot --report --batch-plot --batch-report --batch-csv --batch-points --batch-stats
ptm batch configs/batches/drain_iv_1k_repeat_linear.yaml --dry-run --summary --batch-csv --batch-points --batch-stats
ptm scheme-plan configs/schemes/drain_iv_1k_recipe_and_batch.yaml
ptm scheme configs/schemes/drain_iv_1k_recipe_and_batch.yaml --dry-run --fake-resistance-ohm 1000 --fake-noise-std-a 0 --summary --plot --report --batch-csv --batch-points --batch-stats --batch-report
ptm scheme-plan configs/schemes/drain_iv_1k_bias_series.yaml
ptm scheme configs/schemes/drain_iv_1k_bias_series.yaml --dry-run --fake-resistance-ohm 1000 --fake-noise-std-a 0 --summary --plot --report
ptm scheme configs/schemes/drain_iv_1k_bias_series.yaml --dry-run --fake-resistance-ohm 1000 --fake-noise-std-a 0 --summary --plot --report --scheme-plot --scheme-runs --scheme-points --scheme-stats
ptm scheme-plan configs/schemes/drain_iv_1k_bias_matrix.yaml
ptm scheme configs/schemes/drain_iv_1k_bias_matrix.yaml --dry-run --fake-resistance-ohm 1000 --fake-noise-std-a 0 --summary --plot --report --scheme-plot --scheme-runs --scheme-points --scheme-stats
ptm scheme-plan configs/schemes/single_gate_dry_run_scheme.yaml
ptm scheme configs/schemes/single_gate_dry_run_scheme.yaml --dry-run --fake-resistance-ohm 1000 --fake-channel-resistance-ohm 1000000 --fake-noise-std-a 0 --summary --plot --report --gate-stats --scheme-runs --scheme-points --scheme-stats
ptm scheme-report data\schemes\<scheme_folder>
ptm scheme-plot data\schemes\<scheme_folder>
ptm scheme-runs data\schemes\<scheme_folder>
ptm scheme-points data\schemes\<scheme_folder>
ptm scheme-stats data\schemes\<scheme_folder>
ptm campaign --name resistor_campaign_check
ptm campaign --name resistor_pass_only --sample resistor_box --device 1k_resistor --tag resistor --qc-status PASS --completed-only --min-resistance-ohm 900 --max-resistance-ohm 1100
ptm campaign --name resistor_analytics_check --sample resistor_box --device 1k_resistor --tag resistor --qc-status PASS --completed-only --min-resistance-ohm 900 --max-resistance-ohm 1100 --analytics
ptm campaign-stats data\campaigns\<campaign_folder>
ptm campaign-histogram data\campaigns\<campaign_folder>
ptm campaign-bundle data\campaigns\<campaign_folder>
ptm feedback-bundle data\raw\<run_folder> --extra-file doctor.json
ptm batch-report data\batches\<batch_folder>
ptm batch-plot data\batches\<batch_folder>
ptm batch-csv data\batches\<batch_folder>
ptm batch-points data\batches\<batch_folder>
ptm batch-stats data\batches\<batch_folder>
ptm list-runs
ptm list-runs --sample resistor_box --tag resistor
ptm rebuild-index
ptm feedback-bundle data\raw\<run_folder> --extra-file doctor.json
ptm inspect-run data\raw\<run_folder>
ptm report data\raw\<run_folder>
ptm summarize data\raw\<run_folder>
ptm plot data\raw\<run_folder>
```

Expected 1 kOhm result:

- `completed=True`
- `points=21`
- fitted resistance near `1000 ohm`
- `0.1 V` point near `1e-4 A`

## Useful Commands

```powershell
ptm list-resources
ptm identify --instrument keithley_2450 --address "GPIB0::2::INSTR"
ptm probe --instrument keithley_2450 --address "GPIB0::2::INSTR"
ptm validate configs/recipes/drain_iv.yaml
ptm plan configs/recipes/drain_iv.yaml
ptm preflight configs/recipes/drain_iv.yaml
ptm new-recipe configs/recipes/my_device_iv.yaml --mode linear_one_way --measurement-name my_device_iv
ptm new-batch configs/batches/my_repeat.yaml --kind repeat --name my_repeat --recipe configs/recipes/my_device_iv.yaml --repeat 3 --interval-s 1.0
ptm new-scheme configs/schemes/my_scheme.yaml --kind recipe_and_batch --name my_scheme --recipe configs/recipes/my_device_iv.yaml --batch configs/batches/my_repeat.yaml
ptm run configs/recipes/drain_iv.yaml --progress --summary --plot --report
ptm run configs/recipes/drain_iv.yaml --progress --summary --plot --report --yes
ptm run configs/recipes/drain_iv_1k_resistor.yaml --dry-run --fake-resistance-ohm 1000 --fake-noise-std-a 0 --summary --report
ptm single-gate-plan configs/recipes/single_gate_dry_run.yaml
ptm single-gate configs/recipes/single_gate_dry_run.yaml --dry-run --progress --fake-channel-resistance-ohm 1000000 --fake-noise-std-a 0
ptm single-gate configs/recipes/single_gate_dry_run.yaml --dry-run --summary --plot --report --gate-stats --fake-channel-resistance-ohm 1000000 --fake-noise-std-a 0
ptm ac-lockin-plan configs/recipes/ac_lockin_dry_run.yaml
ptm ac-lockin configs/recipes/ac_lockin_dry_run.yaml --dry-run --summary --plot --report --fake-resistance-ohm 1000000 --fake-lockin-r-v 0.000002 --fake-lockin-phase-deg 30 --fake-noise-std 0
ptm pulse-plan configs/recipes/pulse_dry_run.yaml
ptm pulse configs/recipes/pulse_dry_run.yaml --dry-run --summary --plot --report --progress --fake-resistance-ohm 1000000 --fake-noise-std-a 0
ptm single-gate-summary data\raw\<single_gate_run_folder>
ptm single-gate-plot data\raw\<single_gate_run_folder>
ptm single-gate-stats data\raw\<single_gate_run_folder>
ptm single-gate-report data\raw\<single_gate_run_folder>
ptm list-runs --measurement-type single_gate_sweep
ptm check-run data\raw\<run_folder>
ptm batch configs/batches/drain_iv_1k_smoke_suite.yaml --dry-run --fake-resistance-ohm 1000 --fake-noise-std-a 0 --summary --plot --report --batch-plot --batch-report --batch-csv --batch-points --batch-stats
ptm batch configs/batches/drain_iv_1k_repeat_linear.yaml --dry-run --summary --batch-csv --batch-points --batch-stats
ptm scheme-plan configs/schemes/drain_iv_1k_recipe_and_batch.yaml
ptm scheme configs/schemes/drain_iv_1k_recipe_and_batch.yaml --dry-run --fake-resistance-ohm 1000 --fake-noise-std-a 0 --summary --plot --report --batch-csv --batch-points --batch-stats --batch-report
ptm scheme-plan configs/schemes/drain_iv_1k_bias_series.yaml
ptm scheme configs/schemes/drain_iv_1k_bias_series.yaml --dry-run --fake-resistance-ohm 1000 --fake-noise-std-a 0 --summary --plot --report
ptm scheme configs/schemes/drain_iv_1k_bias_series.yaml --dry-run --fake-resistance-ohm 1000 --fake-noise-std-a 0 --summary --plot --report --scheme-plot --scheme-runs --scheme-points --scheme-stats
ptm scheme-plan configs/schemes/drain_iv_1k_bias_matrix.yaml
ptm scheme configs/schemes/drain_iv_1k_bias_matrix.yaml --dry-run --fake-resistance-ohm 1000 --fake-noise-std-a 0 --summary --plot --report --scheme-plot --scheme-runs --scheme-points --scheme-stats
ptm scheme-plan configs/schemes/single_gate_dry_run_scheme.yaml
ptm scheme configs/schemes/single_gate_dry_run_scheme.yaml --dry-run --fake-resistance-ohm 1000 --fake-channel-resistance-ohm 1000000 --fake-noise-std-a 0 --summary --plot --report --gate-stats --scheme-runs --scheme-points --scheme-stats
ptm scheme-report data\schemes\<scheme_folder>
ptm scheme-plot data\schemes\<scheme_folder>
ptm scheme-runs data\schemes\<scheme_folder>
ptm scheme-points data\schemes\<scheme_folder>
ptm scheme-stats data\schemes\<scheme_folder>
ptm campaign --name resistor_campaign_check
ptm campaign --name resistor_pass_only --sample resistor_box --device 1k_resistor --tag resistor --qc-status PASS --completed-only --min-resistance-ohm 900 --max-resistance-ohm 1100
ptm campaign --name resistor_analytics_check --sample resistor_box --device 1k_resistor --tag resistor --qc-status PASS --completed-only --min-resistance-ohm 900 --max-resistance-ohm 1100 --analytics
ptm campaign-stats data\campaigns\<campaign_folder>
ptm campaign-histogram data\campaigns\<campaign_folder>
ptm campaign-bundle data\campaigns\<campaign_folder>
ptm batch-report data\batches\<batch_folder>
ptm batch-plot data\batches\<batch_folder>
ptm batch-csv data\batches\<batch_folder>
ptm batch-points data\batches\<batch_folder>
ptm batch-stats data\batches\<batch_folder>
ptm list-runs
ptm list-runs --sample resistor_box --tag resistor
ptm rebuild-index
ptm inspect-run data\raw\<run_folder>
ptm report data\raw\<run_folder>
ptm summarize data\raw\<run_folder>
ptm plot data\raw\<run_folder>
```

See `docs/phase0_hardware_smoke_test.md` for the Phase 0 completion checklist.
See `docs/phase1_reliable_dc_iv.md` for the current DC I-V improvements.

Use `ptm plan <recipe>` to inspect the exact sweep shape before touching
hardware. Hardware `ptm run` commands print the same plan, run preflight
automatically, and ask for confirmation before enabling the Keithley output. Use
`--yes` only when the recipe and wiring have already been checked and you
intentionally want an unattended run. `--dry-run` never prompts.

Use `ptm batch <batch.yaml>` for a session made of multiple recipes. Batch runs
write each normal run folder plus a session-level `batch_summary.json` under
`data/batches`. Batch entries can use `repeat` and `interval_s` for repeated
stability checks. Add `--batch-plot --batch-report --batch-csv --batch-points
--batch-stats` to create an overlay plot, Markdown session report, per-run CSV
table, long-form point table, and grouped stability CSV, or regenerate them
later with `ptm batch-plot`, `ptm batch-report`, `ptm batch-csv`,
`ptm batch-points`, and `ptm batch-stats`.

The 1 kOhm recipes include quality checks for completion, point count, and
fitted resistance from `900 ohm` to `1100 ohm`. Use `ptm check-run <run_dir>` to
re-evaluate saved runs. For dry-runs, use `--fake-resistance-ohm 1000
--fake-noise-std-a 0` to simulate the resistor smoke test all the way through
QC PASS. See `docs/phase3_quality_checks.md`.

Use `ptm scheme <scheme.yaml>` when one measurement workflow should combine
single recipes and batch sessions. Scheme hardware runs preflight every nested
recipe before enabling output, asks once for confirmation, and writes
`scheme_summary.json`, `scheme_report.md`, and `scheme_steps.csv` under
`data/schemes`. See `docs/phase4_measurement_schemes.md`.

Scheme recipe steps can also define `overrides` to change sweep parameters,
metadata, instrument range/address, output folder, or checks without copying the
base recipe file. See `configs/schemes/drain_iv_1k_bias_series.yaml` and
`docs/phase5_scheme_overrides.md`.

For sweep series, use a scheme `matrix` to expand one recipe step into multiple
row-specific measurement conditions. See
`configs/schemes/drain_iv_1k_bias_matrix.yaml` and
`docs/phase7_scheme_parameter_matrix.md`.

Use `--scheme-plot --scheme-runs --scheme-points --scheme-stats` to export a
completed scheme as an overlay SVG, per-run CSV, long-form point CSV, and grouped
statistics CSV. Existing scheme folders can be regenerated with `ptm
scheme-report`, `ptm scheme-plot`, `ptm scheme-runs`, `ptm scheme-points`, and
`ptm scheme-stats`. See `docs/phase6_scheme_review_exports.md`.

Use `ptm campaign --name <name>` after a measurement session to create a
campaign-level manifest, run CSV, and Markdown report across `data/raw`,
`data/batches`, and `data/schemes`. See `docs/phase8_campaign_manifest.md`.
Add campaign filters such as `--sample`, `--device`, `--tag`, `--qc-status`,
`--completed-only`, and resistance windows to curate a smaller analysis set.
See `docs/phase9_campaign_curation.md`.
Add `--analytics` to write grouped resistance statistics and a resistance
histogram, or regenerate them later with `ptm campaign-stats` and
`ptm campaign-histogram`. See `docs/phase10_campaign_analytics.md`.
Use `ptm campaign-bundle data\campaigns\<campaign_folder>` to create a portable
folder plus ZIP archive containing the campaign artifacts, selected run files,
and batch/scheme summaries. Add `--no-points`, `--no-plots`, or `--no-reports`
for smaller bundles. See `docs/phase11_campaign_bundle.md`.

Use `ptm single-gate-plan <recipe>` and `ptm single-gate <recipe>` for the
first gate/drain two-SMU workflow. The current milestone is dry-run verified;
hardware runs require separate drain and gate Keithley addresses in the recipe.
See `docs/phase12_single_gate_sweep.md`.
Add `--summary --plot --report --gate-stats` to create single-gate review
artifacts, or regenerate them later with `ptm single-gate-summary`,
`ptm single-gate-plot`, `ptm single-gate-stats`, and `ptm single-gate-report`.
See `docs/phase13_single_gate_review_exports.md`.
Drain I-V and single-gate runs can coexist in `data/raw`; `inspect-run`,
`list-runs`, campaigns, and campaign bundles understand both run types. Use
`ptm list-runs --measurement-type single_gate_sweep` to filter. See
`docs/phase14_mixed_run_support.md`.
Scheme YAML can now include `type: single_gate` steps alongside Drain I-V and
batch steps. See `configs/schemes/single_gate_dry_run_scheme.yaml` and
`docs/phase15_single_gate_schemes.md`.

The GUI `Schemes` workspace can build, validate, plan, dry-run, and review
scheme YAML. `Dry Run Scheme` uses the same fake-instrument core as CLI
dry-runs, then shows the saved scheme summary and Markdown report in the GUI.
The same workspace can refresh saved scheme folders from `data/schemes` or a
selected source folder, reload older scheme reports, and compare selected
scheme/step statistics. Hardware scheme execution remains CLI/future-smoke-test
gated.

4-probe hardware, active SR860 hardware acquisition, pulse hardware, and GUI
hardware support beyond guarded Drain I-V are intentionally kept as future
method milestones for now. The current architecture notes and TODO list are in
`docs/phase16_method_extensibility_roadmap.md`.
