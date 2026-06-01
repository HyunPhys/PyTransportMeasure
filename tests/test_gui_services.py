from pathlib import Path

from pytransport.gui_services import GuiFakeSettings, available_gui_methods, format_gui_plan, run_gui_dry_run


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
