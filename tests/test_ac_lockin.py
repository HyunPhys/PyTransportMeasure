import csv
import json
from pathlib import Path

import pytest

from pytransport.ac_lockin import ac_lockin_point_count, format_ac_lockin_plan, run_ac_lockin_sweep
from pytransport.ac_lockin_review import (
    format_ac_lockin_summary,
    summarize_ac_lockin_run,
    write_ac_lockin_plot_svg,
    write_ac_lockin_report,
)
from pytransport.instruments.fake import FakeLockIn, FakeSMU
from pytransport.recipes import AcLockInRecipe, load_ac_lockin_recipe, load_named_safety_preset


def ac_lockin_recipe_data(output_dir: Path) -> dict:
    return {
        "measurement_name": "ac_lockin_test",
        "safety_preset": "nano_device_safe",
        "experiment": {"sample_id": "sim", "device_id": "lockin_dev", "tags": ["ac-lockin"]},
        "source_instrument": {
            "id": "keithley_2450",
            "address": "GPIB0::2::INSTR",
            "voltage_range_v": 0.1,
            "current_range_a": 1e-6,
        },
        "lockin": {
            "enabled": True,
            "address": "GPIB0::4::INSTR",
            "channels": ["x", "y", "r", "theta"],
            "read_timing": "after_dc_settle",
            "reference_source": "internal",
            "reference_frequency_hz": 17.777,
            "sine_output_amplitude_v": 0.01,
            "input_mode": "voltage",
            "voltage_input": "a",
            "input_coupling": "ac",
            "input_grounding": "float",
            "voltage_input_range_v": 0.01,
            "sensitivity_index": 18,
            "time_constant_index": 10,
            "filter_slope_db_per_oct": 24,
            "synchronous_filter": False,
        },
        "bias_sweep": {
            "mode": "linear_one_way",
            "start_v": -0.05,
            "stop_v": 0.05,
            "points": 5,
            "delay_s": 0.0,
            "current_compliance_a": 1e-6,
        },
        "output": {"directory": output_dir},
        "checks": {"require_completed": True, "min_points": 5},
    }


def test_ac_lockin_recipe_sample_and_plan():
    recipe = load_ac_lockin_recipe("configs/recipes/ac_lockin_dry_run.yaml")
    safety = load_named_safety_preset(recipe.safety_preset)
    plan = format_ac_lockin_plan(recipe, safety, "configs/recipes/ac_lockin_dry_run.yaml")

    assert recipe.measurement_name == "ac_lockin_dry_run"
    assert ac_lockin_point_count(recipe) == 11
    assert "AC Lock-In Sweep Plan" in plan
    assert "Measurement geometry: two_terminal, 2-terminal" in plan
    assert "Lock-in timing: after_dc_settle" in plan
    assert "Lock-in read settle: 0 s" in plan
    assert "Lock-in reference frequency: 17.777 Hz" in plan
    assert "Lock-in filter slope: 24 dB/oct" in plan


def test_ac_lockin_hardware_smoke_recipe_is_conservative():
    recipe = load_ac_lockin_recipe("configs/recipes/ac_lockin_hardware_smoke.yaml")
    safety = load_named_safety_preset(recipe.safety_preset)
    plan = format_ac_lockin_plan(recipe, safety, "configs/recipes/ac_lockin_hardware_smoke.yaml")

    assert recipe.measurement_name == "ac_lockin_hardware_smoke"
    assert recipe.source_instrument.nplc == pytest.approx(1.0)
    assert recipe.bias_sweep.current_compliance_a <= 1e-7
    assert recipe.lockin.reference_frequency_hz == pytest.approx(17.777)
    assert recipe.lockin.time_constant_index == 10
    assert recipe.lockin.settle_time_constants == pytest.approx(3.0)
    assert ac_lockin_point_count(recipe) == 5
    assert "Source NPLC: 1.0" in plan
    assert "Lock-in time constant: 0.1 s" in plan
    assert "Lock-in read settle: 0.3 s" in plan
    assert "Lock-in sine output amplitude: 0.01 V" in plan


def test_ac_lockin_dry_run_writes_points_metadata_and_artifacts(tmp_path):
    recipe = AcLockInRecipe.model_validate(ac_lockin_recipe_data(tmp_path))
    safety = load_named_safety_preset(recipe.safety_preset)
    source = FakeSMU(resistance_ohm=1_000_000, noise_std_a=0)
    lockin = FakeLockIn(signal_r_v=2e-6, phase_deg=30, noise_std_v=0)

    metadata = run_ac_lockin_sweep(recipe, safety, source, lockin, recipe_path="ac_lockin.yaml")

    assert metadata["completed"] is True
    assert metadata["measurement_type"] == "ac_lockin_sweep"
    assert metadata["points_written"] == 5
    assert metadata["lockin_time_constant_s"] == pytest.approx(0.1)
    assert metadata["lockin_read_settle_s"] == pytest.approx(0.0)
    assert source.is_output_on is False
    assert lockin.connected is False
    run_dir = Path(metadata["run_dir"])
    rows = list(csv.DictReader((run_dir / "points.csv").open(newline="", encoding="utf-8")))
    saved_metadata = json.loads((run_dir / "metadata.json").read_text(encoding="utf-8"))
    assert len(rows) == 5
    assert float(rows[0]["lockin_r_v"]) == pytest.approx(2e-6)
    assert saved_metadata["lockin_probe"]["idn"] == "FAKE,LOCKIN,SR860-DRY-RUN,0"
    assert saved_metadata["configured_source_smu"]["current_compliance_a"] == pytest.approx(1e-6)
    assert saved_metadata["configured_source_smu"]["voltage_range_v"] == pytest.approx(0.1)

    summary = summarize_ac_lockin_run(run_dir)
    assert summary.points == 5
    assert summary.lockin_r_max_v == pytest.approx(2e-6)
    assert "AC lock-in run:" in format_ac_lockin_summary(summary)
    assert write_ac_lockin_plot_svg(run_dir).name == "ac_lockin_plot.svg"
    assert write_ac_lockin_report(run_dir).name == "ac_lockin_report.md"


def test_ac_lockin_compliance_stop_saves_partial_and_turns_off(tmp_path):
    data = ac_lockin_recipe_data(tmp_path)
    recipe = AcLockInRecipe.model_validate(data)
    safety = load_named_safety_preset(recipe.safety_preset)
    source = FakeSMU(resistance_ohm=10_000, noise_std_a=0)
    lockin = FakeLockIn(signal_r_v=1e-6, phase_deg=0, noise_std_v=0)

    metadata = run_ac_lockin_sweep(recipe, safety, source, lockin)

    assert metadata["completed"] is False
    assert metadata["error_type"] == "SafetyLimitError"
    assert metadata["triggered_limit"] == "source_instrument_compliance"
    assert source.is_output_on is False
    assert lockin.connected is False


def test_ac_lockin_recipe_requires_enabled_lockin(tmp_path):
    data = ac_lockin_recipe_data(tmp_path)
    data["lockin"] = {"enabled": False}

    with pytest.raises(Exception, match="lockin.enabled=true"):
        AcLockInRecipe.model_validate(data)
