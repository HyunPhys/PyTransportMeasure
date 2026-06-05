import csv
import json
from pathlib import Path

import pytest

from pytransport.instruments.fake import CoupledFakeDeviceState, CoupledFakeSMU
from pytransport.recipes import SingleGateRecipe, load_named_safety_preset, load_single_gate_recipe
from pytransport.single_gate import format_single_gate_plan, run_single_gate_sweep, single_gate_point_count


def single_gate_recipe_data(output_dir: Path) -> dict:
    return {
        "measurement_name": "single_gate_test",
        "safety_preset": "nano_device_safe",
        "experiment": {"sample_id": "sim", "device_id": "fet", "tags": ["single-gate"]},
        "drain_instrument": {
            "id": "keithley_2450",
            "address": "GPIB0::2::INSTR",
            "voltage_range_v": 0.2,
            "current_range_a": 1e-6,
        },
        "gate_instrument": {
            "id": "keithley_2450",
            "address": "GPIB0::3::INSTR",
            "voltage_range_v": 1.0,
            "current_range_a": 1e-9,
        },
        "gate_sweep": {
            "start_v": -0.5,
            "stop_v": 0.5,
            "points": 3,
            "settle_s": 0.0,
            "current_compliance_a": 1e-8,
        },
        "drain_sweep": {
            "mode": "linear_one_way",
            "start_v": -0.1,
            "stop_v": 0.1,
            "points": 5,
            "delay_s": 0.0,
            "current_compliance_a": 1e-6,
        },
        "output": {"directory": output_dir},
        "checks": {"require_completed": True, "min_points": 15},
    }


def build_fake_pair(channel_resistance_ohm: float = 1_000_000.0) -> tuple[CoupledFakeSMU, CoupledFakeSMU]:
    state = CoupledFakeDeviceState(
        channel_resistance_ohm=channel_resistance_ohm,
        gate_leak_resistance_ohm=1_000_000_000.0,
        noise_std_a=0.0,
    )
    return CoupledFakeSMU("drain", state), CoupledFakeSMU("gate", state)


def test_single_gate_recipe_validation_and_plan(tmp_path):
    recipe = SingleGateRecipe.model_validate(single_gate_recipe_data(tmp_path))
    safety = load_named_safety_preset(recipe.safety_preset)

    assert single_gate_point_count(recipe) == 15
    plan = format_single_gate_plan(recipe, safety, "single_gate.yaml")
    assert "Single-Gate Sweep Plan" in plan
    assert "Measurement geometry: two_terminal, 2-terminal" in plan
    assert "Total points: 15" in plan


def test_load_single_gate_recipe_sample():
    recipe = load_single_gate_recipe("configs/recipes/single_gate_dry_run.yaml")

    assert recipe.measurement_name == "single_gate_dry_run"
    assert single_gate_point_count(recipe) == 55


def test_load_single_gate_hardware_smoke_recipe_and_safety():
    recipe = load_single_gate_recipe("configs/recipes/single_gate_hardware_smoke.yaml")
    safety = load_named_safety_preset(recipe.safety_preset)
    plan = format_single_gate_plan(recipe, safety, "configs/recipes/single_gate_hardware_smoke.yaml")

    assert recipe.measurement_name == "single_gate_hardware_smoke"
    assert recipe.drain_instrument.address != recipe.gate_instrument.address
    assert single_gate_point_count(recipe) == 15
    assert safety.max_abs_voltage_v == 0.2
    assert "Total points: 15" in plan


def test_single_gate_dry_run_writes_csv_and_metadata(tmp_path):
    recipe = SingleGateRecipe.model_validate(single_gate_recipe_data(tmp_path))
    safety = load_named_safety_preset(recipe.safety_preset)
    drain_smu, gate_smu = build_fake_pair()

    metadata = run_single_gate_sweep(recipe, safety, drain_smu, gate_smu, recipe_path="single_gate.yaml")

    assert metadata["completed"] is True
    assert metadata["points_written"] == 15
    run_dir = Path(metadata["run_dir"])
    rows = list(csv.DictReader((run_dir / "points.csv").open(newline="", encoding="utf-8")))
    saved_metadata = json.loads((run_dir / "metadata.json").read_text(encoding="utf-8"))
    assert len(rows) == 15
    assert rows[0]["gate_voltage_v"] == "-0.5"
    assert rows[0]["drain_voltage_v"] == "-0.1"
    assert saved_metadata["measurement_type"] == "single_gate_sweep"
    assert saved_metadata["drain_instrument_probe"]["idn"].startswith("FAKE,DRAIN-SMU")
    assert saved_metadata["gate_instrument_probe"]["idn"].startswith("FAKE,GATE-SMU")
    assert saved_metadata["configured_drain_smu"]["current_compliance_a"] == pytest.approx(1e-6)
    assert saved_metadata["configured_drain_smu"]["voltage_range_v"] == pytest.approx(0.2)
    assert saved_metadata["configured_gate_smu"]["current_compliance_a"] == pytest.approx(1e-8)
    assert saved_metadata["configured_gate_smu"]["current_range_a"] == pytest.approx(1e-9)
    assert drain_smu.is_output_on is False
    assert gate_smu.is_output_on is False


def test_single_gate_compliance_stop_saves_partial_metadata(tmp_path):
    data = single_gate_recipe_data(tmp_path)
    data["drain_sweep"]["current_compliance_a"] = 1e-6
    recipe = SingleGateRecipe.model_validate(data)
    safety = load_named_safety_preset(recipe.safety_preset)
    drain_smu, gate_smu = build_fake_pair(channel_resistance_ohm=10_000.0)

    metadata = run_single_gate_sweep(recipe, safety, drain_smu, gate_smu)

    assert metadata["completed"] is False
    assert metadata["error_type"] == "SafetyLimitError"
    assert metadata["triggered_limit"] == "drain_instrument_compliance"
    saved_metadata = json.loads(Path(metadata["metadata_path"]).read_text(encoding="utf-8"))
    assert saved_metadata["points_written"] == 0
    assert drain_smu.is_output_on is False
    assert gate_smu.is_output_on is False


def test_single_gate_rejects_gate_voltage_over_safety(tmp_path):
    data = single_gate_recipe_data(tmp_path)
    data["gate_sweep"]["stop_v"] = 2.0
    data["gate_instrument"]["voltage_range_v"] = 2.5
    recipe = SingleGateRecipe.model_validate(data)
    safety = load_named_safety_preset(recipe.safety_preset)
    drain_smu, gate_smu = build_fake_pair()

    with pytest.raises(Exception, match="above safety limit"):
        run_single_gate_sweep(recipe, safety, drain_smu, gate_smu)
