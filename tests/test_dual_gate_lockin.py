import csv
import json
from pathlib import Path

import pytest

from pytransport.dual_gate_lockin import dual_gate_lockin_point_count, format_dual_gate_lockin_plan, run_dual_gate_lockin_sweep
from pytransport.dual_gate_lockin_review import (
    format_dual_gate_lockin_summary,
    summarize_dual_gate_lockin_run,
    write_dual_gate_lockin_heatmap_svg,
    write_dual_gate_lockin_report,
    write_dual_gate_lockin_stats_csv,
)
from pytransport.instruments.fake import DualGateFakeDeviceState, DualGateFakeLockIn, DualGateFakeSMU
from pytransport.recipes import DualGateLockInRecipe, load_dual_gate_lockin_recipe, load_named_safety_preset


def dual_gate_lockin_recipe_data(output_dir: Path) -> dict:
    return {
        "measurement_name": "dual_gate_lockin_test",
        "safety_preset": "nano_device_safe",
        "experiment": {"sample_id": "sim", "device_id": "dual_gate_lockin", "tags": ["dual-gate", "lock-in"]},
        "measurement_geometry": {"terminal_count": 2, "method": "two_terminal"},
        "gate1_instrument": {
            "id": "keithley_2450",
            "address": "GPIB0::2::INSTR",
            "voltage_range_v": 0.2,
            "current_range_a": 1e-9,
            "nplc": 1.0,
        },
        "gate2_instrument": {
            "id": "keithley_2450",
            "address": "GPIB0::3::INSTR",
            "voltage_range_v": 0.2,
            "current_range_a": 1e-9,
            "nplc": 1.0,
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
        "gate1_sweep": {
            "start_v": -0.1,
            "stop_v": 0.1,
            "points": 3,
            "settle_s": 0.0,
            "current_compliance_a": 1e-8,
        },
        "gate2_sweep": {
            "start_v": -0.1,
            "stop_v": 0.1,
            "points": 3,
            "settle_s": 0.0,
            "current_compliance_a": 1e-8,
        },
        "output": {"directory": output_dir},
        "checks": {"require_completed": True, "min_points": 9},
    }


def build_fake_dual_gate_lockin() -> tuple[DualGateFakeSMU, DualGateFakeSMU, DualGateFakeLockIn]:
    state = DualGateFakeDeviceState(
        gate1_leak_resistance_ohm=1_000_000_000.0,
        gate2_leak_resistance_ohm=1_000_000_000.0,
    )
    lockin = DualGateFakeLockIn(
        state,
        base_r_v=2e-6,
        gate1_sensitivity_v_per_v=1e-6,
        gate2_sensitivity_v_per_v=-5e-7,
        phase_deg=30,
        noise_std_v=0,
    )
    return DualGateFakeSMU("gate1", state), DualGateFakeSMU("gate2", state), lockin


def test_dual_gate_lockin_recipe_sample_and_plan():
    recipe = load_dual_gate_lockin_recipe("configs/recipes/dual_gate_lockin_dry_run.yaml")
    safety = load_named_safety_preset(recipe.safety_preset)
    plan = format_dual_gate_lockin_plan(recipe, safety, "configs/recipes/dual_gate_lockin_dry_run.yaml")

    assert recipe.measurement_name == "dual_gate_lockin_dry_run"
    assert recipe.gate1_instrument.nplc == pytest.approx(1.0)
    assert recipe.gate2_instrument.nplc == pytest.approx(1.0)
    assert recipe.lockin.reference_frequency_hz == pytest.approx(17.777)
    assert recipe.lockin.sensitivity_index == 18
    assert dual_gate_lockin_point_count(recipe) == 25
    assert "Dual-Gate Lock-In Sweep Plan" in plan
    assert "Lock-in timing: after_dc_settle" in plan
    assert "Lock-in reference source: internal" in plan
    assert "Lock-in time constant index: 10" in plan
    assert "Total points: 25" in plan


def test_dual_gate_lockin_dry_run_writes_points_metadata_and_artifacts(tmp_path):
    recipe = DualGateLockInRecipe.model_validate(dual_gate_lockin_recipe_data(tmp_path))
    safety = load_named_safety_preset(recipe.safety_preset)
    gate1_smu, gate2_smu, lockin = build_fake_dual_gate_lockin()

    metadata = run_dual_gate_lockin_sweep(recipe, safety, gate1_smu, gate2_smu, lockin, recipe_path="dual_gate_lockin.yaml")

    assert metadata["completed"] is True
    assert metadata["measurement_type"] == "dual_gate_lockin_sweep"
    assert metadata["points_written"] == 9
    assert gate1_smu.is_output_on is False
    assert gate2_smu.is_output_on is False
    assert lockin.connected is False
    run_dir = Path(metadata["run_dir"])
    rows = list(csv.DictReader((run_dir / "points.csv").open(newline="", encoding="utf-8")))
    saved_metadata = json.loads((run_dir / "metadata.json").read_text(encoding="utf-8"))
    assert len(rows) == 9
    assert rows[0]["gate1_voltage_v"] == "-0.1"
    assert rows[0]["gate2_voltage_v"] == "-0.1"
    assert float(rows[0]["lockin_r_v"]) > 0
    assert saved_metadata["lockin_probe"]["idn"].startswith("FAKE,LOCKIN,DUAL-GATE")

    summary = summarize_dual_gate_lockin_run(run_dir)
    assert summary.points == 9
    assert summary.gate1_points == 3
    assert summary.gate2_points == 3
    assert "Dual-gate lock-in run:" in format_dual_gate_lockin_summary(summary)
    assert write_dual_gate_lockin_stats_csv(run_dir).name == "dual_gate_lockin_stats.csv"
    assert write_dual_gate_lockin_heatmap_svg(run_dir).name == "dual_gate_lockin_heatmap.svg"
    assert write_dual_gate_lockin_report(run_dir).name == "dual_gate_lockin_report.md"


def test_dual_gate_lockin_gate_compliance_stop_saves_partial(tmp_path):
    data = dual_gate_lockin_recipe_data(tmp_path)
    data["gate1_sweep"]["current_compliance_a"] = 1e-9
    recipe = DualGateLockInRecipe.model_validate(data)
    safety = load_named_safety_preset(recipe.safety_preset)
    state = DualGateFakeDeviceState(gate1_leak_resistance_ohm=1_000_000.0)
    gate1_smu = DualGateFakeSMU("gate1", state)
    gate2_smu = DualGateFakeSMU("gate2", state)
    lockin = DualGateFakeLockIn(state, base_r_v=1e-6, noise_std_v=0)

    metadata = run_dual_gate_lockin_sweep(recipe, safety, gate1_smu, gate2_smu, lockin)

    assert metadata["completed"] is False
    assert metadata["error_type"] == "SafetyLimitError"
    assert metadata["triggered_limit"] == "gate1_instrument_compliance"
    assert gate1_smu.is_output_on is False
    assert gate2_smu.is_output_on is False
