from pathlib import Path

import pytest

from pytransport.gui_services import (
    GuiFakeSettings,
    available_gui_methods,
    create_gui_feedback_bundle,
    default_recipe_text,
    drain_iv_form_from_text,
    drain_iv_text_from_form,
    format_hardware_confirmation_text,
    format_gui_plan,
    format_gui_plan_text,
    format_gui_progress,
    list_gui_runs,
    load_gui_saved_run,
    primary_plot_path,
    primary_report_path,
    run_gui_doctor_text,
    run_gui_preflight_text,
    run_gui_hardware_text,
    save_recipe_text,
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


def test_gui_plan_uses_method_registry():
    plan = format_gui_plan("pulse_measurement", "configs/recipes/pulse_dry_run.yaml")

    assert "Pulse Measurement Plan" in plan
    assert "pulse_dry_run" in plan


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


def test_gui_preflight_text_rejects_non_drain_method():
    text = Path("configs/recipes/pulse_dry_run.yaml").read_text(encoding="utf-8")

    with pytest.raises(ValueError, match="Drain I-V"):
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
