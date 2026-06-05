import csv
import json
from pathlib import Path

import pytest

from pytransport.dual_gate import dual_gate_point_count, format_dual_gate_plan, run_dual_gate_sweep
from pytransport.dual_gate_review import (
    format_dual_gate_summary,
    summarize_dual_gate_run,
    write_dual_gate_heatmap_svg,
    write_dual_gate_report,
    write_dual_gate_stats_csv,
)
from pytransport.instruments.fake import DualGateFakeDeviceState, DualGateFakeSMU
from pytransport.recipes import DualGateRecipe, load_dual_gate_recipe, load_named_safety_preset


def dual_gate_recipe_data(output_dir: Path) -> dict:
    return {
        "measurement_name": "dual_gate_test",
        "safety_preset": "nano_device_safe",
        "experiment": {"sample_id": "sim", "device_id": "dual_gate", "tags": ["dual-gate"]},
        "measurement_geometry": {
            "terminal_count": 2,
            "method": "two_terminal",
            "notes": "test geometry",
        },
        "drain_instrument": {
            "id": "keithley_2450",
            "address": "GPIB0::2::INSTR",
            "voltage_range_v": 0.1,
            "current_range_a": 1e-6,
            "nplc": 1.0,
        },
        "gate1_instrument": {
            "id": "keithley_2450",
            "address": "GPIB0::3::INSTR",
            "voltage_range_v": 0.2,
            "current_range_a": 1e-9,
            "nplc": 1.0,
        },
        "gate2_instrument": {
            "id": "keithley_2450",
            "address": "GPIB0::4::INSTR",
            "voltage_range_v": 0.2,
            "current_range_a": 1e-9,
            "nplc": 1.0,
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
        "drain_sweep": {
            "mode": "linear_one_way",
            "start_v": -0.02,
            "stop_v": 0.02,
            "points": 5,
            "delay_s": 0.0,
            "current_compliance_a": 1e-7,
        },
        "output": {"directory": output_dir},
        "checks": {"require_completed": True, "min_points": 45},
    }


def build_fake_triple(channel_resistance_ohm: float = 1_000_000.0) -> tuple[DualGateFakeSMU, DualGateFakeSMU, DualGateFakeSMU]:
    state = DualGateFakeDeviceState(
        channel_resistance_ohm=channel_resistance_ohm,
        gate1_leak_resistance_ohm=1_000_000_000.0,
        gate2_leak_resistance_ohm=1_000_000_000.0,
        gate1_modulation_per_v=0.1,
        gate2_modulation_per_v=-0.05,
        noise_std_a=0.0,
    )
    return DualGateFakeSMU("drain", state), DualGateFakeSMU("gate1", state), DualGateFakeSMU("gate2", state)


def test_dual_gate_recipe_sample_and_plan():
    recipe = load_dual_gate_recipe("configs/recipes/dual_gate_dry_run.yaml")
    safety = load_named_safety_preset(recipe.safety_preset)
    plan = format_dual_gate_plan(recipe, safety, "configs/recipes/dual_gate_dry_run.yaml")

    assert recipe.measurement_name == "dual_gate_dry_run"
    assert recipe.gate1_instrument.nplc == pytest.approx(1.0)
    assert recipe.gate2_instrument.nplc == pytest.approx(1.0)
    assert dual_gate_point_count(recipe) == 125
    assert "Dual-Gate Sweep Plan" in plan
    assert "Measurement geometry: two_terminal, 2-terminal" in plan
    assert "Total points: 125" in plan


def test_dual_gate_dry_run_writes_points_metadata_and_artifacts(tmp_path):
    recipe = DualGateRecipe.model_validate(dual_gate_recipe_data(tmp_path))
    safety = load_named_safety_preset(recipe.safety_preset)
    drain_smu, gate1_smu, gate2_smu = build_fake_triple()

    metadata = run_dual_gate_sweep(recipe, safety, drain_smu, gate1_smu, gate2_smu, recipe_path="dual_gate.yaml")

    assert metadata["completed"] is True
    assert metadata["measurement_type"] == "dual_gate_sweep"
    assert metadata["points_written"] == 45
    assert drain_smu.is_output_on is False
    assert gate1_smu.is_output_on is False
    assert gate2_smu.is_output_on is False
    run_dir = Path(metadata["run_dir"])
    rows = list(csv.DictReader((run_dir / "points.csv").open(newline="", encoding="utf-8")))
    saved_metadata = json.loads((run_dir / "metadata.json").read_text(encoding="utf-8"))
    assert len(rows) == 45
    assert rows[0]["gate1_voltage_v"] == "-0.1"
    assert rows[0]["gate2_voltage_v"] == "-0.1"
    assert rows[0]["drain_voltage_v"] == "-0.02"
    assert saved_metadata["gate1_instrument_probe"]["idn"].startswith("FAKE,GATE1-SMU")
    assert saved_metadata["gate2_instrument_probe"]["idn"].startswith("FAKE,GATE2-SMU")
    assert saved_metadata["configured_drain_smu"]["current_compliance_a"] == pytest.approx(1e-7)
    assert saved_metadata["configured_drain_smu"]["nplc"] == pytest.approx(1.0)
    assert saved_metadata["configured_gate1_smu"]["current_compliance_a"] == pytest.approx(1e-8)
    assert saved_metadata["configured_gate2_smu"]["current_range_a"] == pytest.approx(1e-9)
    assert saved_metadata["configured_drain_smu_readback"]["current_nplc"] == "1"
    assert saved_metadata["configured_gate1_smu_readback"]["source_current_limit"] == "1e-08"
    assert saved_metadata["configured_gate2_smu_readback"]["current_range"] == "1e-09"

    summary = summarize_dual_gate_run(run_dir)
    assert summary.points == 45
    assert summary.gate1_points == 3
    assert summary.gate2_points == 3
    assert "Dual-gate run:" in format_dual_gate_summary(summary)
    assert write_dual_gate_stats_csv(run_dir).name == "dual_gate_stats.csv"
    assert write_dual_gate_heatmap_svg(run_dir).name == "dual_gate_heatmap.svg"
    assert write_dual_gate_report(run_dir).name == "dual_gate_report.md"


def test_dual_gate_compliance_stop_saves_partial_and_turns_off(tmp_path):
    recipe = DualGateRecipe.model_validate(dual_gate_recipe_data(tmp_path))
    safety = load_named_safety_preset(recipe.safety_preset)
    drain_smu, gate1_smu, gate2_smu = build_fake_triple(channel_resistance_ohm=10_000.0)

    metadata = run_dual_gate_sweep(recipe, safety, drain_smu, gate1_smu, gate2_smu)

    assert metadata["completed"] is False
    assert metadata["error_type"] == "SafetyLimitError"
    assert metadata["triggered_limit"] == "drain_instrument_compliance"
    assert drain_smu.is_output_on is False
    assert gate1_smu.is_output_on is False
    assert gate2_smu.is_output_on is False
