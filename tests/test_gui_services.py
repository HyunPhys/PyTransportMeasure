import json
from pathlib import Path

import pytest

from pytransport.gui_services import (
    GuiFakeSettings,
    GuiState,
    GuiSchemeStepDraft,
    available_gui_methods,
    compare_gui_schemes,
    create_gui_feedback_bundle,
    default_scheme_text,
    default_recipe_text,
    drain_iv_form_from_text,
    drain_iv_text_from_form,
    format_hardware_confirmation_text,
    format_gui_plan,
    format_gui_plan_text,
    format_gui_progress,
    format_recipe_overview_text,
    refresh_gui_instruments,
    list_gui_runs,
    list_gui_schemes,
    load_gui_saved_run,
    load_gui_saved_scheme,
    load_gui_state,
    load_recipe_from_text,
    primary_plot_path,
    primary_report_path,
    run_gui_doctor_text,
    run_gui_communication_test,
    run_gui_preflight_text,
    run_gui_hardware_text,
    run_gui_scheme_dry_run_text,
    save_recipe_text,
    save_gui_state,
    schema_form_from_text,
    schema_form_text_from_values,
    scheme_builder_from_text,
    scheme_plot_series,
    scheme_text_from_builder,
    validate_scheme_text,
    write_gui_scheme_comparison_csv,
    format_scheme_plan_text,
    validate_recipe_text,
    run_gui_dry_run,
    run_gui_dry_run_text,
)
from pytransport.instruments.fake import FakeSMU


def test_gui_methods_include_dry_run_families():
    methods = available_gui_methods()

    assert methods["drain_iv"] == "Drain I-V"
    assert methods["single_gate_sweep"] == "Single-gate sweep"
    assert methods["ac_lockin_sweep"] == "AC lock-in sweep"
    assert methods["pulse_measurement"] == "Pulse measurement"


def test_gui_scheme_builder_generates_valid_scheme_text():
    text = scheme_text_from_builder(
        "gui_test_scheme",
        True,
        [
            GuiSchemeStepDraft("drain_iv", "drain", "../recipes/drain_iv_1k_resistor.yaml"),
            GuiSchemeStepDraft("single_gate", "gate", "../recipes/single_gate_dry_run.yaml", repeat=2, interval_s=0.1),
        ],
    )

    name, stop_on_error, rows = scheme_builder_from_text(text)
    ok, validation = validate_scheme_text(text, scheme_path="configs/schemes/gui_test_scheme.yaml")
    plan = format_scheme_plan_text(text, scheme_path="configs/schemes/gui_test_scheme.yaml", preview_points=1)

    assert name == "gui_test_scheme"
    assert stop_on_error is True
    assert rows[0].type == "drain_iv"
    assert rows[1].repeat == 2
    assert ok is True
    assert "Scheme validation: PASS" in validation
    assert "Enabled steps: 3" in plan
    assert "drain" in plan
    assert "gate_rep02" in plan


def test_gui_scheme_builder_supports_drain_iv_sweep_overrides():
    text = scheme_text_from_builder(
        "gui_override_scheme",
        True,
        [
            GuiSchemeStepDraft(
                "drain_iv",
                "small_span",
                "../recipes/drain_iv_1k_resistor.yaml",
                measurement_suffix="_small",
                sweep_start_v="-0.05",
                sweep_stop_v="0.05",
                sweep_points="5",
            ),
        ],
    )
    name, _stop_on_error, rows = scheme_builder_from_text(text)
    plan = format_scheme_plan_text(text, scheme_path="configs/schemes/gui_override_scheme.yaml", preview_points=5)

    assert name == "gui_override_scheme"
    assert rows[0].measurement_suffix == "_small"
    assert rows[0].sweep_start_v == "-0.05"
    assert rows[0].sweep_stop_v == "0.05"
    assert rows[0].sweep_points == "5"
    assert "measurement_suffix: _small" in plan
    assert "sweep.start_v: -0.05" in plan
    assert "sweep.stop_v: 0.05" in plan
    assert "sweep.points: 5" in plan


def test_gui_default_scheme_text_is_loadable():
    name, _stop_on_error, rows = scheme_builder_from_text(default_scheme_text())

    assert name == "gui_scheme"
    assert [row.type for row in rows] == ["drain_iv", "single_gate"]


def test_gui_scheme_dry_run_text_writes_scheme_artifacts(tmp_path):
    text = scheme_text_from_builder(
        "gui_scheme_dry_run",
        True,
        [
            GuiSchemeStepDraft(
                "drain_iv",
                "small_drain",
                "../recipes/drain_iv_1k_resistor.yaml",
                measurement_suffix="_scheme",
                sweep_start_v="-0.05",
                sweep_stop_v="0.05",
            ),
        ],
    )

    result = run_gui_scheme_dry_run_text(
        text,
        scheme_path="configs/schemes/gui_scheme_dry_run.yaml",
        fake=GuiFakeSettings(resistance_ohm=1000, noise_std_a=0),
        index_path=tmp_path / "index.jsonl",
        draft_dir=tmp_path / "drafts",
        output_dir=tmp_path / "schemes",
    )

    assert result.summary_path.exists()
    assert result.scheme_dir.exists()
    assert Path(result.artifact_paths["report_path"]).exists()
    assert Path(result.artifact_paths["scheme_runs_path"]).exists()
    assert "Scheme dry-run: gui_scheme_dry_run" in result.summary_text
    assert "Scheme quality: PASS" in result.summary_text
    assert "# gui_scheme_dry_run" in result.report_text


def test_gui_saved_scheme_browser_lists_and_loads_summary(tmp_path):
    scheme_dir = tmp_path / "schemes" / "20260605_saved_scheme"
    batch_dir = scheme_dir / "batches" / "batch-a"
    run_dir = tmp_path / "raw" / "run-a"
    scheme_dir.mkdir(parents=True)
    batch_dir.mkdir(parents=True)
    run_dir.mkdir(parents=True)
    (run_dir / "points.csv").write_text("index,voltage_v,current_a,elapsed_s\n0,0,0,0\n", encoding="utf-8")
    (scheme_dir / "scheme_report.md").write_text("# saved_scheme\n", encoding="utf-8")
    batch_summary_path = batch_dir / "batch_summary.json"
    batch_summary_path.write_text(json.dumps({"runs": [{"label": "a"}, {"label": "b"}]}), encoding="utf-8")
    summary = {
        "scheme_name": "saved_scheme",
        "scheme_path": "configs/schemes/saved_scheme.yaml",
        "started_at": "2026-06-05T12:00:00",
        "finished_at": "2026-06-05T12:01:00",
        "dry_run": True,
        "completed": True,
        "quality": {"status": "PASS", "results": []},
        "steps": [
            {
                "type": "drain_iv",
                "label": "first",
                "completed": True,
                "run_dir": str(run_dir),
                "quality": {"status": "PASS", "results": []},
            },
            {
                "type": "batch",
                "label": "repeat",
                "completed": True,
                "batch_summary_path": str(batch_summary_path),
            }
        ],
    }
    (scheme_dir / "scheme_summary.json").write_text(json.dumps(summary), encoding="utf-8")

    records = list_gui_schemes(tmp_path / "schemes")
    result = load_gui_saved_scheme(scheme_dir)

    assert records[0]["scheme_name"] == "saved_scheme"
    assert records[0]["quality_status"] == "PASS"
    assert records[0]["step_count"] == 2
    assert records[0]["run_count"] == 3
    assert result.scheme_dir == scheme_dir
    assert "Saved scheme: saved_scheme" in result.summary_text
    assert "# saved_scheme" in result.report_text
    assert "report_path" in result.artifact_paths


def test_gui_saved_scheme_load_generates_report_text_without_report_file(tmp_path):
    scheme_dir = tmp_path / "schemes" / "20260605_saved_scheme_no_report"
    scheme_dir.mkdir(parents=True)
    summary = {
        "scheme_name": "saved_scheme_no_report",
        "scheme_path": "configs/schemes/saved_scheme_no_report.yaml",
        "started_at": "2026-06-05T12:00:00",
        "finished_at": "2026-06-05T12:01:00",
        "dry_run": True,
        "completed": True,
        "quality": {"status": "PASS", "results": []},
        "steps": [],
    }
    (scheme_dir / "scheme_summary.json").write_text(json.dumps(summary), encoding="utf-8")

    result = load_gui_saved_scheme(scheme_dir)

    assert "# saved_scheme_no_report" in result.report_text
    assert "report_path" not in result.artifact_paths


def test_gui_scheme_comparison_builds_step_stats_from_saved_schemes(tmp_path):
    scheme_a = write_saved_scheme_for_compare(tmp_path, "scheme_a", 1000.0)
    scheme_b = write_saved_scheme_for_compare(tmp_path, "scheme_b", 2000.0)

    comparison = compare_gui_schemes([scheme_a, scheme_b, scheme_a])

    assert "Scheme Comparison" in comparison.text
    assert "Schemes: 2" in comparison.text
    assert len(comparison.rows) == 2
    assert [row["scheme_name"] for row in comparison.rows] == ["scheme_a", "scheme_b"]
    assert comparison.rows[0]["step_label"] == "iv"
    assert comparison.rows[0]["runs"] == 1
    assert comparison.rows[0]["mean_fitted_resistance_ohm"] == pytest.approx(1000.0)
    assert comparison.rows[1]["mean_fitted_resistance_ohm"] == pytest.approx(2000.0)


def test_gui_scheme_filters_and_comparison_csv_export(tmp_path):
    scheme_a = write_saved_scheme_for_compare(tmp_path, "keep_scheme", 1000.0)
    scheme_b = write_saved_scheme_for_compare(tmp_path, "drop_scheme", 2000.0)
    comparison = compare_gui_schemes([scheme_a, scheme_b])
    output = tmp_path / "exports" / "comparison.csv"

    records = list_gui_schemes(tmp_path / "schemes", name_contains="keep", completed=True, dry_run=True, quality_status="PASS")
    csv_path = write_gui_scheme_comparison_csv(comparison, output)

    assert [record["scheme_name"] for record in records] == ["keep_scheme"]
    text = csv_path.read_text(encoding="utf-8")
    assert "scheme_name,step_label,started_at" in text
    assert "keep_scheme,iv" in text
    assert "drop_scheme,iv" in text


def test_gui_state_load_save_round_trip_and_defaults(tmp_path):
    state_path = tmp_path / "gui_state.json"

    assert load_gui_state(state_path) == GuiState()

    saved = save_gui_state(GuiState(run_source_dir="lab/raw", scheme_source_dir="lab/schemes"), state_path)
    loaded = load_gui_state(saved)

    assert loaded.run_source_dir == "lab/raw"
    assert loaded.scheme_source_dir == "lab/schemes"

    state_path.write_text("{bad json", encoding="utf-8")
    assert load_gui_state(state_path) == GuiState()


def test_gui_scheme_plot_series_reads_plottable_saved_runs(tmp_path):
    scheme_dir = write_saved_scheme_for_compare(tmp_path, "scheme_overlay", 1500.0)

    series = scheme_plot_series(scheme_dir)

    assert len(series) == 1
    assert series[0][0] == "iv"
    assert series[0][1] == [(0.0, 0.0), (0.0015, 1e-06)]


def write_saved_scheme_for_compare(tmp_path: Path, name: str, resistance_ohm: float) -> Path:
    scheme_dir = tmp_path / "schemes" / name
    run_dir = tmp_path / "raw" / name
    scheme_dir.mkdir(parents=True)
    run_dir.mkdir(parents=True)
    current_a = 1e-6
    voltage_v = resistance_ohm * current_a
    (run_dir / "points.csv").write_text(
        f"voltage_v,current_a\n0,0\n{voltage_v},{current_a}\n",
        encoding="utf-8",
    )
    (run_dir / "metadata.json").write_text(
        json.dumps({"completed": True, "measurement_name": name, "run_dir": str(run_dir)}),
        encoding="utf-8",
    )
    summary = {
        "scheme_name": name,
        "scheme_path": f"configs/schemes/{name}.yaml",
        "started_at": "2026-06-05T12:00:00",
        "finished_at": "2026-06-05T12:01:00",
        "dry_run": True,
        "completed": True,
        "quality": {"status": "PASS", "results": []},
        "steps": [
            {
                "type": "drain_iv",
                "label": "iv",
                "completed": True,
                "run_dir": str(run_dir),
                "quality": {"status": "PASS", "results": []},
            }
        ],
    }
    (scheme_dir / "scheme_summary.json").write_text(json.dumps(summary), encoding="utf-8")
    return scheme_dir


def test_gui_instrument_refresh_formats_resources():
    resources, text = refresh_gui_instruments(resource_lister=lambda: ("GPIB0::2::INSTR", "ASRL1::INSTR"))

    assert resources == ("GPIB0::2::INSTR", "ASRL1::INSTR")
    assert "Detected VISA resources" in text
    assert "GPIB0::2::INSTR" in text


def test_gui_communication_test_uses_selected_address():
    text = run_gui_communication_test(
        "GPIB0::2::INSTR",
        resource_lister=lambda: ("GPIB0::2::INSTR",),
        probe_factory=lambda address, timeout: {"idn": f"KEITHLEY,{address}", "language": "SCPI"},
    )

    assert "OK: True" in text
    assert "Requested address: GPIB0::2::INSTR" in text
    assert "KEITHLEY,GPIB0::2::INSTR" in text


def test_gui_plan_uses_method_registry():
    plan = format_gui_plan("pulse_measurement", "configs/recipes/pulse_dry_run.yaml")

    assert "Pulse Measurement Plan" in plan
    assert "pulse_dry_run" in plan


def test_gui_recipe_overview_summarizes_drain_iv_recipe():
    overview = format_recipe_overview_text("drain_iv", default_recipe_text("drain_iv"))

    assert "Recipe Overview" in overview
    assert "Method: Drain I-V (drain_iv)" in overview
    assert "Measurement: drain_iv_1k_resistor_check" in overview
    assert "Experiment" in overview
    assert "- sample id: resistor_box" in overview
    assert "Instrument" in overview
    assert "- address: GPIB0::2::INSTR" in overview
    assert "Sweep" in overview
    assert "- points: 21" in overview


def test_gui_recipe_overview_is_method_aware_for_pulse_recipe():
    overview = format_recipe_overview_text("pulse_measurement", default_recipe_text("pulse_measurement"))

    assert "Method: Pulse measurement (pulse_measurement)" in overview
    assert "Source Instrument" in overview
    assert "Pulse" in overview
    assert "- amplitude v:" in overview
    assert "Pulse Limits" in overview


def test_schema_form_round_trips_drain_iv_common_fields():
    text = default_recipe_text("drain_iv")
    sections = schema_form_from_text("drain_iv", text)
    fields = {field.path: field for section in sections for field in section.fields}

    assert "measurement_name" in fields
    assert fields["measurement_name"].value == "drain_iv_1k_resistor_check"
    assert fields["experiment.cooldown_id"].value == ""
    assert fields["instrument.terminal"].kind == "choice"
    assert "" in fields["instrument.terminal"].choices
    assert fields["instrument.nplc"].value == "1"
    assert fields["sweep.points"].value == "21"

    updated = schema_form_text_from_values(
        "drain_iv",
        text,
        {
            "measurement_name": "schema_form_drain",
            "experiment.cooldown_id": "cd-schema",
            "sweep.points": "11",
            "checks.min_points": "11",
        },
    )
    round_trip = drain_iv_form_from_text(updated)

    assert round_trip["measurement_name"] == "schema_form_drain"
    assert round_trip["cooldown_id"] == "cd-schema"
    assert round_trip["points"] == "11"
    assert round_trip["min_points"] == "11"


def test_schema_form_treats_blank_optional_numbers_as_none():
    text = default_recipe_text("drain_iv")

    updated = schema_form_text_from_values(
        "drain_iv",
        text,
        {
            "instrument.voltage_range_v": "",
            "instrument.current_range_a": "",
            "instrument.nplc": "",
            "checks.fitted_resistance_ohm.min_ohm": "",
            "checks.fitted_resistance_ohm.max_ohm": "",
        },
    )
    recipe = load_recipe_from_text("drain_iv", updated)

    assert recipe.instrument.voltage_range_v is None
    assert recipe.instrument.current_range_a is None
    assert recipe.instrument.nplc is None
    assert recipe.checks.fitted_resistance_ohm.min_ohm is None
    assert recipe.checks.fitted_resistance_ohm.max_ohm is None


def test_schema_form_supports_pulse_recipe_values():
    text = default_recipe_text("pulse_measurement")
    sections = schema_form_from_text("pulse_measurement", text)
    fields = {field.path: field for section in sections for field in section.fields}

    assert "source_instrument.address" in fields
    assert "pulse.amplitude_v" in fields
    assert "pulse_limits.max_abs_pulse_v" in fields

    updated = schema_form_text_from_values(
        "pulse_measurement",
        text,
        {
            "measurement_name": "schema_form_pulse",
            "pulse.count": "7",
            "checks.min_points": "7",
        },
    )
    recipe = load_recipe_from_text("pulse_measurement", updated)

    assert recipe.measurement_name == "schema_form_pulse"
    assert recipe.pulse.count == 7
    assert recipe.checks.min_points == 7


def test_gui_recipe_editor_validates_default_recipe_text(tmp_path):
    text = default_recipe_text("pulse_measurement")
    ok, message = validate_recipe_text("pulse_measurement", text)

    assert ok is True
    assert "Validation: PASS" in message
    assert "Pulse Measurement Plan" in message

    output = save_recipe_text("pulse_measurement", text, tmp_path / "saved_pulse.yaml")
    assert output.exists()


def test_gui_recipe_editor_reports_schema_errors():
    ok, message = validate_recipe_text("drain_iv", "measurement_name: bad\n")

    assert ok is False
    assert "Validation: FAIL" in message


def test_drain_iv_form_round_trips_lab_context_fields():
    values = drain_iv_form_from_text(Path("configs/recipes/drain_iv_1k_resistor.yaml").read_text(encoding="utf-8"))
    values["cooldown_id"] = "cd-2026-06"
    values["contact_geometry"] = "2-probe wirebond"
    values["contact_notes"] = "outer Au pads"
    values["lab_notebook_ref"] = "ELN-42 p.7"

    text = drain_iv_text_from_form(values)
    round_trip = drain_iv_form_from_text(text)

    assert round_trip["cooldown_id"] == "cd-2026-06"
    assert round_trip["contact_geometry"] == "2-probe wirebond"
    assert round_trip["contact_notes"] == "outer Au pads"
    assert round_trip["lab_notebook_ref"] == "ELN-42 p.7"


def test_gui_dry_run_writes_artifacts_for_drain_iv(tmp_path):
    recipe_path = tmp_path / "drain.yaml"
    recipe_path.write_text(
        """
measurement_name: gui_drain
safety_preset: nano_device_safe
experiment:
  sample_id: gui
  device_id: drain
instrument:
  id: keithley_2450
  address: GPIB0::2::INSTR
  voltage_range_v: 0.1
  current_range_a: 1.0e-6
sweep:
  mode: linear_one_way
  start_v: -0.05
  stop_v: 0.05
  points: 5
  delay_s: 0.0
  current_compliance_a: 1.0e-6
output:
  directory: {output}
checks:
  require_completed: true
  min_points: 5
""".format(output=str(tmp_path).replace("\\", "/")),
        encoding="utf-8",
    )

    result = run_gui_dry_run(
        "drain_iv",
        recipe_path,
        fake=GuiFakeSettings(resistance_ohm=1_000_000, noise_std_a=0),
        index_path=tmp_path / "index.jsonl",
    )

    assert result.metadata["completed"] is True
    assert result.metadata["measurement_type"] == "drain_iv"
    assert result.run_dir.exists()
    assert Path(result.metadata["plot_path"]).exists()
    assert Path(result.metadata["report_path"]).exists()
    assert "Quality: PASS" in result.quality_text
    assert "Run:" in result.summary_text


def test_gui_dry_run_writes_artifacts_for_pulse(tmp_path):
    recipe_path = tmp_path / "pulse.yaml"
    recipe_path.write_text(
        """
measurement_name: gui_pulse
safety_preset: nano_device_safe
experiment:
  sample_id: gui
  device_id: pulse
source_instrument:
  id: keithley_2450
  address: GPIB0::2::INSTR
  voltage_range_v: 0.2
  current_range_a: 1.0e-6
pulse:
  base_v: 0.0
  amplitude_v: 0.1
  width_s: 0.001
  period_s: 0.01
  count: 5
  current_compliance_a: 1.0e-6
  acquisition: pulse_end
pulse_limits:
  max_abs_pulse_v: 0.2
  max_pulse_width_s: 0.01
  max_duty_cycle: 0.2
  max_pulse_count: 100
  max_total_on_time_s: 0.1
output:
  directory: {output}
checks:
  require_completed: true
  min_points: 5
""".format(output=str(tmp_path).replace("\\", "/")),
        encoding="utf-8",
    )

    result = run_gui_dry_run(
        "pulse_measurement",
        recipe_path,
        fake=GuiFakeSettings(resistance_ohm=1_000_000, noise_std_a=0),
        index_path=tmp_path / "index.jsonl",
    )

    assert result.metadata["completed"] is True
    assert result.metadata["measurement_type"] == "pulse_measurement"
    assert Path(result.metadata["pulse_plot_path"]).exists()
    assert Path(result.metadata["pulse_report_path"]).exists()
    assert "Pulse run:" in result.summary_text


def test_gui_run_browser_lists_and_loads_indexed_runs(tmp_path):
    recipe_path = tmp_path / "pulse.yaml"
    recipe_path.write_text(
        """
measurement_name: gui_browser_pulse
safety_preset: nano_device_safe
experiment:
  sample_id: gui
  device_id: browser
source_instrument:
  id: keithley_2450
  address: GPIB0::2::INSTR
  voltage_range_v: 0.2
  current_range_a: 1.0e-6
pulse:
  base_v: 0.0
  amplitude_v: 0.1
  width_s: 0.001
  period_s: 0.01
  count: 5
  current_compliance_a: 1.0e-6
  acquisition: pulse_end
pulse_limits:
  max_abs_pulse_v: 0.2
  max_pulse_width_s: 0.01
  max_duty_cycle: 0.2
  max_pulse_count: 100
  max_total_on_time_s: 0.1
output:
  directory: {output}
checks:
  require_completed: true
  min_points: 5
""".format(output=str(tmp_path).replace("\\", "/")),
        encoding="utf-8",
    )
    index_path = tmp_path / "index.jsonl"
    result = run_gui_dry_run(
        "pulse_measurement",
        recipe_path,
        fake=GuiFakeSettings(resistance_ohm=1_000_000, noise_std_a=0),
        index_path=index_path,
    )

    records = list_gui_runs(index_path)
    loaded = load_gui_saved_run(result.run_dir)

    assert records[0]["measurement_name"] == "gui_browser_pulse"
    assert loaded.metadata["measurement_name"] == "gui_browser_pulse"
    assert "Pulse run:" in loaded.summary_text
    assert "Quality: PASS" in loaded.quality_text


def test_gui_primary_artifact_paths_use_existing_files(tmp_path):
    plot = tmp_path / "plot.svg"
    report = tmp_path / "report.md"
    plot.write_text("<svg></svg>", encoding="utf-8")
    report.write_text("# report\n", encoding="utf-8")
    metadata = {
        "plot_path": str(tmp_path / "missing.svg"),
        "pulse_plot_path": str(plot),
        "report_path": str(report),
    }

    assert primary_plot_path(metadata) == plot
    assert primary_report_path(metadata) == report


def test_list_gui_runs_filters_lab_context_and_status(tmp_path):
    index_path = tmp_path / "index.jsonl"
    index_path.write_text(
        "\n".join(
            [
                '{"measurement_name": "a", "run_dir": "run-a", "sample_id": "s1", "device_id": "d1", "cooldown_id": "cd1", "tags": ["keep"], "completed": true, "measurement_type": "drain_iv"}',
                '{"measurement_name": "b", "run_dir": "run-b", "sample_id": "s2", "device_id": "d2", "cooldown_id": "cd2", "tags": ["drop"], "completed": false, "error_type": "SafetyLimitError", "measurement_type": "drain_iv"}',
                '{"measurement_name": "c", "run_dir": "run-c", "sample_id": "s1", "device_id": "d3", "cooldown_id": "cd1", "tags": ["keep"], "completed": false, "interrupted": true, "measurement_type": "single_gate_sweep"}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    assert [record["run_dir"] for record in list_gui_runs(index_path, sample_id="s1", cooldown_id="cd1")] == ["run-c", "run-a"]
    assert [record["run_dir"] for record in list_gui_runs(index_path, tag="keep", measurement_type="drain_iv")] == ["run-a"]
    assert [record["run_dir"] for record in list_gui_runs(index_path, failed=True)] == ["run-b"]
    assert [record["run_dir"] for record in list_gui_runs(index_path, interrupted=True)] == ["run-c"]


def test_list_gui_runs_can_scan_selected_source_directory(tmp_path):
    raw_dir = tmp_path / "raw"
    run_a = raw_dir / "run-a"
    run_b = raw_dir / "run-b"
    run_a.mkdir(parents=True)
    run_b.mkdir()
    (run_a / "metadata.json").write_text(
        '{"started_at": "2026-06-05T10:00:00", "measurement_name": "a", "completed": true, "points_written": 2, "run_dir": "run-a", "recipe": {"experiment": {"sample_id": "s1", "cooldown_id": "cd1"}}}',
        encoding="utf-8",
    )
    (run_b / "metadata.json").write_text(
        '{"started_at": "2026-06-05T11:00:00", "measurement_name": "b", "completed": true, "points_written": 3, "run_dir": "run-b", "recipe": {"experiment": {"sample_id": "s2", "cooldown_id": "cd2"}}}',
        encoding="utf-8",
    )
    index_path = tmp_path / "unused_index.jsonl"

    records = list_gui_runs(index_path, source_dir=raw_dir, sample_id="s2")

    assert [record["measurement_name"] for record in records] == ["b"]
    assert [record["measurement_name"] for record in list_gui_runs(index_path, source_dir=run_a)] == ["a"]


def test_drain_iv_form_round_trip_from_default_recipe():
    text = Path("configs/recipes/drain_iv_1k_resistor.yaml").read_text(encoding="utf-8")
    values = drain_iv_form_from_text(text)

    assert values["measurement_name"] == "drain_iv_1k_resistor_check"
    assert values["address"] == "GPIB0::2::INSTR"
    assert values["sweep_mode"] == "linear_one_way"
    assert values["points"] == "21"
    assert values["resistance_min_ohm"] == "900"

    values["measurement_name"] = "gui_form_round_trip"
    values["points"] = "11"
    updated = drain_iv_text_from_form(values)
    round_trip = drain_iv_form_from_text(updated)

    assert round_trip["measurement_name"] == "gui_form_round_trip"
    assert round_trip["points"] == "11"
    assert round_trip["current_compliance_a"] == "0.0002"


def test_drain_iv_form_rejects_missing_required_field():
    text = Path("configs/recipes/drain_iv_1k_resistor.yaml").read_text(encoding="utf-8")
    values = drain_iv_form_from_text(text)
    values["address"] = ""

    with pytest.raises(ValueError, match="address is required"):
        drain_iv_text_from_form(values)


def test_gui_plan_text_uses_unsaved_editor_yaml(tmp_path):
    values = drain_iv_form_from_text(Path("configs/recipes/drain_iv_1k_resistor.yaml").read_text(encoding="utf-8"))
    values["measurement_name"] = "unsaved_gui_plan"
    values["points"] = "7"
    values["output_directory"] = str(tmp_path).replace("\\", "/")
    text = drain_iv_text_from_form(values)

    plan = format_gui_plan_text("drain_iv", text, preview_points=7)

    assert "unsaved_gui_plan" in plan
    assert "points: 7" in plan or "Points: 7" in plan


def test_gui_dry_run_text_uses_unsaved_editor_yaml(tmp_path):
    values = drain_iv_form_from_text(Path("configs/recipes/drain_iv_1k_resistor.yaml").read_text(encoding="utf-8"))
    values["measurement_name"] = "unsaved_gui_dry_run"
    values["points"] = "9"
    values["min_points"] = "9"
    values["output_directory"] = str(tmp_path).replace("\\", "/")
    text = drain_iv_text_from_form(values)

    result = run_gui_dry_run_text(
        "drain_iv",
        text,
        fake=GuiFakeSettings(resistance_ohm=1000, noise_std_a=0),
        index_path=tmp_path / "index.jsonl",
        draft_dir=tmp_path / "drafts",
    )

    assert result.metadata["measurement_name"] == "unsaved_gui_dry_run"
    assert result.metadata["points_written"] == 9
    assert Path(result.metadata["plot_path"]).exists()
    assert Path(result.metadata["report_path"]).exists()
    assert (tmp_path / "drafts" / "drain_iv_unsaved_gui_dry_run.yaml").exists()


def test_gui_dry_run_text_emits_progress_lines(tmp_path):
    values = drain_iv_form_from_text(Path("configs/recipes/drain_iv_1k_resistor.yaml").read_text(encoding="utf-8"))
    values["measurement_name"] = "gui_progress_dry_run"
    values["points"] = "4"
    values["min_points"] = "4"
    values["output_directory"] = str(tmp_path).replace("\\", "/")
    text = drain_iv_text_from_form(values)
    progress = []

    result = run_gui_dry_run_text(
        "drain_iv",
        text,
        fake=GuiFakeSettings(resistance_ohm=1000, noise_std_a=0),
        index_path=tmp_path / "index.jsonl",
        draft_dir=tmp_path / "drafts",
        progress_callback=lambda point, total: progress.append(format_gui_progress(point, total)),
    )

    assert result.metadata["points_written"] == 4
    assert len(progress) == 4
    assert progress[0].startswith("1/4")
    assert "V=" in progress[0]
    assert "I=" in progress[0]


def test_gui_dry_run_text_stop_request_saves_partial(tmp_path):
    values = drain_iv_form_from_text(Path("configs/recipes/drain_iv_1k_resistor.yaml").read_text(encoding="utf-8"))
    values["measurement_name"] = "gui_stop_dry_run"
    values["points"] = "6"
    values["min_points"] = ""
    values["require_completed"] = "false"
    values["output_directory"] = str(tmp_path).replace("\\", "/")
    text = drain_iv_text_from_form(values)
    progress = []

    result = run_gui_dry_run_text(
        "drain_iv",
        text,
        fake=GuiFakeSettings(resistance_ohm=1000, noise_std_a=0),
        index_path=tmp_path / "index.jsonl",
        draft_dir=tmp_path / "drafts",
        progress_callback=lambda point, total: progress.append(format_gui_progress(point, total)),
        stop_requested=lambda: len(progress) >= 2,
    )

    assert result.metadata["completed"] is False
    assert result.metadata["interrupted"] is True
    assert result.metadata["points_written"] == 2
    assert result.metadata["error_type"] == "KeyboardInterrupt"
    assert Path(result.metadata["metadata_path"]).exists()


def test_gui_preflight_text_uses_unsaved_editor_yaml(tmp_path):
    values = drain_iv_form_from_text(Path("configs/recipes/drain_iv_1k_resistor.yaml").read_text(encoding="utf-8"))
    values["measurement_name"] = "unsaved_gui_preflight"
    values["address"] = "GPIB0::9::INSTR"
    values["output_directory"] = str(tmp_path).replace("\\", "/")
    text = drain_iv_text_from_form(values)

    report = run_gui_preflight_text(
        "drain_iv",
        text,
        resource_lister=lambda: ("GPIB0::9::INSTR",),
        probe_factory=lambda address, timeout: {
            "address": address,
            "idn": "KEITHLEY INSTRUMENTS,MODEL 2450,123,1.0",
            "language": "SCPI",
            "system_error": '0,"No error"',
        },
        draft_dir=tmp_path / "drafts",
    )

    assert "unsaved_gui_preflight" in report
    assert "Recipe address found: True" in report
    assert "Preflight OK: True" in report
    assert (tmp_path / "drafts" / "drain_iv_unsaved_gui_preflight.yaml").exists()


def test_gui_preflight_text_supports_single_gate_editor_yaml(tmp_path):
    text = Path("configs/recipes/single_gate_hardware_smoke.yaml").read_text(encoding="utf-8").replace(
        "single_gate_hardware_smoke",
        "gui_single_gate_preflight",
    )

    report = run_gui_preflight_text(
        "single_gate_sweep",
        text,
        resource_lister=lambda: ("GPIB0::2::INSTR", "GPIB0::3::INSTR"),
        probe_factory=lambda address, timeout: {
            "address": address,
            "idn": f"KEITHLEY INSTRUMENTS,MODEL 2450,{address},1.0",
            "language": "SCPI",
            "system_error": '0,"No error"',
        },
        draft_dir=tmp_path / "drafts",
    )

    assert "gui_single_gate_preflight" in report
    assert "Drain/gate addresses distinct: True" in report
    assert "Single-gate preflight OK: True" in report
    assert (tmp_path / "drafts" / "single_gate_sweep_gui_single_gate_preflight.yaml").exists()


def test_gui_doctor_text_uses_drain_iv_editor_address(tmp_path):
    values = drain_iv_form_from_text(Path("configs/recipes/drain_iv_1k_resistor.yaml").read_text(encoding="utf-8"))
    values["address"] = "GPIB0::8::INSTR"
    values["output_directory"] = str(tmp_path).replace("\\", "/")
    text = drain_iv_text_from_form(values)

    report = run_gui_doctor_text(
        "drain_iv",
        text,
        resource_lister=lambda: ("GPIB0::8::INSTR",),
        probe_factory=lambda address, timeout: {
            "address": address,
            "idn": "KEITHLEY INSTRUMENTS,MODEL 2450,123,1.0",
            "language": "SCPI",
            "system_error": '0,"No error"',
        },
    )

    assert "OK: True" in report
    assert "Requested address: GPIB0::8::INSTR" in report
    assert "Address found: True" in report
    assert "MODEL 2450" in report


def test_gui_doctor_text_can_run_without_method_address():
    report = run_gui_doctor_text(
        "pulse_measurement",
        "measurement_name: placeholder\n",
        resource_lister=lambda: ("ASRL1::INSTR",),
    )

    assert "OK: True" in report
    assert "ASRL1::INSTR" in report
    assert "Requested address" not in report


def test_gui_preflight_text_rejects_unsupported_method():
    text = Path("configs/recipes/pulse_dry_run.yaml").read_text(encoding="utf-8")

    with pytest.raises(ValueError, match="Drain I-V and single-gate"):
        run_gui_preflight_text("pulse_measurement", text)


def test_hardware_confirmation_text_summarizes_editor_recipe(tmp_path):
    values = drain_iv_form_from_text(Path("configs/recipes/drain_iv_1k_resistor.yaml").read_text(encoding="utf-8"))
    values["measurement_name"] = "gui_confirm_summary"
    values["address"] = "GPIB0::7::INSTR"
    values["output_directory"] = str(tmp_path).replace("\\", "/")
    text = drain_iv_text_from_form(values)

    message = format_hardware_confirmation_text("drain_iv", text)

    assert "turn Keithley output ON" in message
    assert "gui_confirm_summary" in message
    assert "GPIB0::7::INSTR" in message
    assert "Compliance: 0.0002 A" in message


def test_gui_hardware_text_runs_after_preflight_with_injected_smu(tmp_path):
    values = drain_iv_form_from_text(Path("configs/recipes/drain_iv_1k_resistor.yaml").read_text(encoding="utf-8"))
    values["measurement_name"] = "gui_hardware_injected"
    values["points"] = "5"
    values["min_points"] = "5"
    values["output_directory"] = str(tmp_path).replace("\\", "/")
    text = drain_iv_text_from_form(values)

    progress = []
    result = run_gui_hardware_text(
        "drain_iv",
        text,
        index_path=tmp_path / "index.jsonl",
        draft_dir=tmp_path / "drafts",
        resource_lister=lambda: ("GPIB0::2::INSTR",),
        probe_factory=lambda address, timeout: {
            "address": address,
            "idn": "KEITHLEY INSTRUMENTS,MODEL 2450,123,1.0",
            "language": "SCPI",
            "system_error": '0,"No error"',
        },
        smu_factory=lambda address, timeout: FakeSMU(resistance_ohm=1000, noise_std_a=0),
        progress_callback=lambda point, total: progress.append(format_gui_progress(point, total)),
    )

    assert result.metadata["completed"] is True
    assert result.metadata["measurement_name"] == "gui_hardware_injected"
    assert result.metadata["points_written"] == 5
    assert len(progress) == 5
    assert progress[-1].startswith("5/5")
    assert Path(result.metadata["plot_path"]).exists()
    assert Path(result.metadata["report_path"]).exists()


def test_gui_hardware_text_blocks_when_preflight_fails(tmp_path):
    values = drain_iv_form_from_text(Path("configs/recipes/drain_iv_1k_resistor.yaml").read_text(encoding="utf-8"))
    values["measurement_name"] = "gui_hardware_blocked"
    values["output_directory"] = str(tmp_path).replace("\\", "/")
    text = drain_iv_text_from_form(values)

    with pytest.raises(RuntimeError, match="preflight did not pass"):
        run_gui_hardware_text(
            "drain_iv",
            text,
            index_path=tmp_path / "index.jsonl",
            draft_dir=tmp_path / "drafts",
            resource_lister=lambda: ("ASRL1::INSTR",),
            smu_factory=lambda address, timeout: FakeSMU(resistance_ohm=1000, noise_std_a=0),
        )


def test_gui_feedback_bundle_helper_creates_zip(tmp_path):
    recipe_path = tmp_path / "drain.yaml"
    recipe_path.write_text(
        """
measurement_name: gui_feedback_bundle
safety_preset: nano_device_safe
instrument:
  id: keithley_2450
  address: GPIB0::2::INSTR
  voltage_range_v: 0.1
  current_range_a: 1.0e-6
sweep:
  mode: linear_one_way
  start_v: -0.01
  stop_v: 0.01
  points: 3
  delay_s: 0.0
  current_compliance_a: 1.0e-6
output:
  directory: {output}
checks:
  require_completed: true
  min_points: 3
""".format(output=str(tmp_path).replace("\\", "/")),
        encoding="utf-8",
    )
    result = run_gui_dry_run(
        "drain_iv",
        recipe_path,
        fake=GuiFakeSettings(resistance_ohm=1_000_000, noise_std_a=0),
        index_path=tmp_path / "index.jsonl",
    )

    zip_path = create_gui_feedback_bundle(result.run_dir, output_dir=tmp_path / "feedback")

    assert zip_path.exists()
    assert zip_path.suffix == ".zip"


def test_gui_feedback_bundle_helper_includes_session_log(tmp_path):
    recipe_path = tmp_path / "drain.yaml"
    recipe_path.write_text(
        """
measurement_name: gui_feedback_bundle_with_log
safety_preset: nano_device_safe
instrument:
  id: keithley_2450
  address: GPIB0::2::INSTR
  voltage_range_v: 0.1
  current_range_a: 1.0e-6
sweep:
  mode: linear_one_way
  start_v: -0.01
  stop_v: 0.01
  points: 3
  delay_s: 0.0
  current_compliance_a: 1.0e-6
output:
  directory: {output}
checks:
  require_completed: true
  min_points: 3
""".format(output=str(tmp_path).replace("\\", "/")),
        encoding="utf-8",
    )
    result = run_gui_dry_run(
        "drain_iv",
        recipe_path,
        fake=GuiFakeSettings(resistance_ohm=1_000_000, noise_std_a=0),
        index_path=tmp_path / "index.jsonl",
    )
    session_log = tmp_path / "gui_session.log"
    session_log.write_text("progress line", encoding="utf-8")

    zip_path = create_gui_feedback_bundle(
        result.run_dir,
        output_dir=tmp_path / "feedback",
        extra_files=[session_log],
    )

    import zipfile

    with zipfile.ZipFile(zip_path) as archive:
        assert "extras/gui_session.log" in archive.namelist()
