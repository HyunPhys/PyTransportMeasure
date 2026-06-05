import csv
import json
from pathlib import Path

import pytest

from pytransport.dual_gate_lockin import (
    dual_gate_lockin_grid_signature,
    dual_gate_lockin_point_count,
    format_dual_gate_lockin_plan,
    planned_dual_gate_lockin_grid,
    run_dual_gate_lockin_sweep,
)
from pytransport.dual_gate_lockin_smoke import run_dual_gate_lockin_active_gate_smoke
from pytransport.dual_gate_lockin_review import (
    audit_dual_gate_lockin_run,
    format_dual_gate_lockin_acceptance,
    format_dual_gate_lockin_summary,
    summarize_dual_gate_lockin_run,
    write_dual_gate_lockin_acceptance_report,
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
        "topology": {
            "device_layout": "hall_bar",
            "gate1_role": "top_gate",
            "gate2_role": "back_gate",
            "source_contact": "S",
            "drain_contact": "D",
            "lockin_input_mode": "voltage",
            "lockin_input_contacts": ["Vxx+", "Vxx-"],
            "excitation_source": "sr860_sine_out",
            "excitation_contacts": ["S", "D"],
            "excitation_amplitude_v": 0.01,
            "current_bias_resistor_ohm": 1_000_000,
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
    assert "Lock-in read settle: 0 s" in plan
    assert "Topology layout: hall_bar" in plan
    assert "Source/drain contacts: S -> D" in plan
    assert "Nominal source-drain AC current: 1e-08 A" in plan
    assert "Total points: 25" in plan
    assert "Scan readiness:" in plan
    assert "Gate grid: 5 x 5 = 25 points" in plan
    assert "Lock-in read settle per point: 0 s" in plan
    assert "Within default point guard: False" in plan


def test_dual_gate_lockin_limited_active_recipe_is_tiny_and_guarded():
    recipe = load_dual_gate_lockin_recipe("configs/recipes/dual_gate_lockin_limited_active.yaml")
    safety = load_named_safety_preset(recipe.safety_preset)
    plan = format_dual_gate_lockin_plan(recipe, safety, "configs/recipes/dual_gate_lockin_limited_active.yaml")

    assert recipe.measurement_name == "dual_gate_lockin_limited_active"
    assert dual_gate_lockin_point_count(recipe) == 4
    assert recipe.gate1_sweep.current_compliance_a <= 1e-8
    assert recipe.gate2_sweep.current_compliance_a <= 1e-8
    assert recipe.lockin.settle_time_constants == pytest.approx(3.0)
    assert "Total points: 4" in plan
    assert "Gate grid: 2 x 2 = 4 points" in plan
    assert "Lock-in read settle: 0.3 s" in plan
    assert "Lock-in read settle per point: 0.3 s" in plan
    assert "Minimum programmed settle time: 2.4 s" in plan
    assert "Within default point guard: True" in plan


def test_dual_gate_lockin_four_terminal_recipe_sample_and_plan():
    recipe = load_dual_gate_lockin_recipe("configs/recipes/dual_gate_lockin_four_terminal_dry_run.yaml")
    safety = load_named_safety_preset(recipe.safety_preset)
    plan = format_dual_gate_lockin_plan(
        recipe,
        safety,
        "configs/recipes/dual_gate_lockin_four_terminal_dry_run.yaml",
    )

    assert recipe.measurement_geometry.method == "four_terminal"
    assert recipe.measurement_geometry.terminal_count == 4
    assert recipe.lockin.input_mode == "voltage"
    assert recipe.lockin.voltage_input == "a-b"
    assert recipe.topology.lockin_input_contacts == ["Vxx+", "Vxx-"]
    assert recipe.topology.excitation_contacts == ["S", "D"]
    assert "Measurement geometry: four_terminal, 4-terminal" in plan
    assert "Lock-in voltage input: a-b" in plan
    assert "Lock-in input: voltage on Vxx+, Vxx-" in plan


def test_dual_gate_lockin_recipe_rejects_incomplete_active_excitation(tmp_path):
    data = dual_gate_lockin_recipe_data(tmp_path)
    data["topology"]["excitation_contacts"] = ["S"]

    with pytest.raises(Exception, match="excitation_contacts must contain exactly two contacts"):
        DualGateLockInRecipe.model_validate(data)


def test_dual_gate_lockin_dry_run_writes_points_metadata_and_artifacts(tmp_path):
    recipe = DualGateLockInRecipe.model_validate(dual_gate_lockin_recipe_data(tmp_path))
    safety = load_named_safety_preset(recipe.safety_preset)
    gate1_smu, gate2_smu, lockin = build_fake_dual_gate_lockin()

    metadata = run_dual_gate_lockin_sweep(recipe, safety, gate1_smu, gate2_smu, lockin, recipe_path="dual_gate_lockin.yaml")

    assert metadata["completed"] is True
    assert metadata["measurement_type"] == "dual_gate_lockin_sweep"
    assert metadata["points_written"] == 9
    assert metadata["planned_points"] == 9
    assert metadata["remaining_points"] == 0
    assert metadata["abort_class"] == "completed"
    assert metadata["last_completed_index"] == 8
    assert metadata["last_completed_gate1_voltage_v"] == pytest.approx(0.1)
    assert metadata["last_completed_gate2_voltage_v"] == pytest.approx(0.1)
    assert metadata["next_point_index"] is None
    assert metadata["recovery_recommendation"] == "run_completed_no_recovery_needed"
    assert metadata["source_drain_excitation_v"] == pytest.approx(0.01)
    assert metadata["source_drain_nominal_current_a"] == pytest.approx(1e-8)
    assert metadata["lockin_time_constant_s"] == pytest.approx(0.1)
    assert metadata["lockin_read_settle_s"] == pytest.approx(0.0)
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
    assert float(rows[0]["source_drain_excitation_v"]) == pytest.approx(0.01)
    assert float(rows[0]["source_drain_nominal_current_a"]) == pytest.approx(1e-8)
    assert float(rows[0]["lockin_resistance_ohm"]) == pytest.approx(float(rows[0]["lockin_r_v"]) / 1e-8)
    assert float(rows[0]["lockin_conductance_s"]) == pytest.approx(1 / float(rows[0]["lockin_resistance_ohm"]))
    assert saved_metadata["lockin_probe"]["idn"].startswith("FAKE,LOCKIN,DUAL-GATE")
    assert saved_metadata["planned_points"] == 9
    assert saved_metadata["planned_gate_grid"] == planned_dual_gate_lockin_grid(recipe)
    assert saved_metadata["planned_gate_grid_signature"] == dual_gate_lockin_grid_signature(recipe)
    assert saved_metadata["planned_gate_grid_signature_algorithm"] == "sha256_json_v1"
    assert saved_metadata["planned_gate_grid"][0] == {
        "index": 0,
        "gate1_index": 0,
        "gate2_index": 0,
        "gate1_voltage_v": -0.1,
        "gate2_voltage_v": -0.1,
    }
    assert saved_metadata["planned_gate_grid"][-1] == {
        "index": 8,
        "gate1_index": 2,
        "gate2_index": 2,
        "gate1_voltage_v": 0.1,
        "gate2_voltage_v": 0.1,
    }
    assert saved_metadata["outputs_off_after_run"] is True
    assert saved_metadata["configured_gate1_smu"]["current_compliance_a"] == pytest.approx(1e-8)
    assert saved_metadata["configured_gate1_smu"]["nplc"] == pytest.approx(1.0)
    assert saved_metadata["configured_gate2_smu"]["current_range_a"] == pytest.approx(1e-9)
    assert saved_metadata["configured_gate1_smu_readback"]["current_nplc"] == "1"
    assert saved_metadata["configured_gate2_smu_readback"]["source_current_limit"] == "1e-08"
    assert saved_metadata["output_state"]["gate1"]["off_after_run"] is True
    assert saved_metadata["output_state"]["gate2"]["off_after_run"] is True
    assert saved_metadata["output_state"]["gate1"]["zero_before_off_succeeded"] is True
    assert saved_metadata["output_state"]["gate1"]["last_commanded_voltage_before_zero_v"] == pytest.approx(0.1)
    assert saved_metadata["output_state"]["gate2"]["last_commanded_voltage_before_zero_v"] == pytest.approx(0.1)
    assert gate1_smu.state.gate1_voltage_v == pytest.approx(0.0)
    assert gate2_smu.state.gate2_voltage_v == pytest.approx(0.0)

    acceptance = audit_dual_gate_lockin_run(run_dir, require_lockin_settings=False)
    assert acceptance.accepted is True
    gate1_leakage_max = max(abs(float(row["gate1_current_a"])) for row in rows)
    gate2_leakage_max = max(abs(float(row["gate2_current_a"])) for row in rows)
    assert acceptance.gate1_leakage_abs_max_a == pytest.approx(gate1_leakage_max)
    assert acceptance.gate2_leakage_abs_max_a == pytest.approx(gate2_leakage_max)
    assert acceptance.gate1_leakage_compliance_margin == pytest.approx(1e-8 / gate1_leakage_max)
    assert acceptance.gate2_leakage_compliance_margin == pytest.approx(1e-8 / gate2_leakage_max)
    assert "Dual-gate lock-in acceptance: PASS" in format_dual_gate_lockin_acceptance(acceptance)
    assert "Gate1 leakage/compliance margin:" in format_dual_gate_lockin_acceptance(acceptance)
    assert write_dual_gate_lockin_acceptance_report(run_dir, require_lockin_settings=False).name == "dual_gate_lockin_acceptance.md"

    strict_acceptance = audit_dual_gate_lockin_run(run_dir)
    assert strict_acceptance.accepted is False
    assert any(issue.check == "lockin_settings" for issue in strict_acceptance.issues)

    summary = summarize_dual_gate_lockin_run(run_dir)
    assert summary.points == 9
    assert summary.gate1_points == 3
    assert summary.gate2_points == 3
    assert summary.lockin_resistance_max_ohm is not None
    assert summary.lockin_conductance_min_s is not None
    assert "Dual-gate lock-in run:" in format_dual_gate_lockin_summary(summary)
    stats_path = write_dual_gate_lockin_stats_csv(run_dir)
    stats_rows = list(csv.DictReader(stats_path.open(newline="", encoding="utf-8")))
    assert stats_path.name == "dual_gate_lockin_stats.csv"
    assert "lockin_resistance_mean_ohm" in stats_rows[0]
    assert "lockin_conductance_mean_s" in stats_rows[0]
    assert write_dual_gate_lockin_heatmap_svg(run_dir).name == "dual_gate_lockin_heatmap.svg"
    assert write_dual_gate_lockin_report(run_dir).name == "dual_gate_lockin_report.md"
    report = (run_dir / "dual_gate_lockin_report.md").read_text(encoding="utf-8")
    assert "## Recovery" in report
    assert "Mean Resistance" in report


def test_dual_gate_lockin_four_terminal_hall_bar_dry_run(tmp_path):
    data = dual_gate_lockin_recipe_data(tmp_path)
    data["measurement_geometry"] = {
        "method": "four_terminal",
        "terminal_count": 4,
        "notes": "SR860 reads differential Hall-bar voltage contacts while gate Keithleys bias gates.",
    }
    data["lockin"]["voltage_input"] = "a-b"
    recipe = DualGateLockInRecipe.model_validate(data)
    safety = load_named_safety_preset(recipe.safety_preset)
    gate1_smu, gate2_smu, lockin = build_fake_dual_gate_lockin()

    metadata = run_dual_gate_lockin_sweep(
        recipe,
        safety,
        gate1_smu,
        gate2_smu,
        lockin,
        recipe_path="dual_gate_lockin_four_terminal.yaml",
    )

    assert metadata["completed"] is True
    assert metadata["points_written"] == 9
    saved_metadata = json.loads(Path(metadata["metadata_path"]).read_text(encoding="utf-8"))
    assert saved_metadata["recipe"]["measurement_geometry"]["method"] == "four_terminal"
    assert saved_metadata["recipe"]["measurement_geometry"]["terminal_count"] == 4
    assert saved_metadata["recipe"]["lockin"]["voltage_input"] == "a-b"
    assert saved_metadata["recipe"]["topology"]["lockin_input_contacts"] == ["Vxx+", "Vxx-"]
    assert saved_metadata["recipe"]["topology"]["excitation_contacts"] == ["S", "D"]
    assert saved_metadata["outputs_off_after_run"] is True


def test_dual_gate_lockin_four_terminal_rejects_voltage_contact_overlap(tmp_path):
    data = dual_gate_lockin_recipe_data(tmp_path)
    data["measurement_geometry"] = {"method": "four_terminal", "terminal_count": 4}
    data["lockin"]["voltage_input"] = "a-b"
    data["topology"]["lockin_input_contacts"] = ["S", "Vxx-"]
    recipe = DualGateLockInRecipe.model_validate(data)
    safety = load_named_safety_preset(recipe.safety_preset)
    gate1_smu, gate2_smu, lockin = build_fake_dual_gate_lockin()

    with pytest.raises(Exception, match="voltage contacts separate from excitation contacts") as error:
        run_dual_gate_lockin_sweep(recipe, safety, gate1_smu, gate2_smu, lockin)
    assert error.value.triggered_limit == "topology_contact_overlap"
    assert gate1_smu.is_output_on is False
    assert gate2_smu.is_output_on is False


def test_dual_gate_lockin_acceptance_fails_output_cleanup_issue(tmp_path):
    recipe = DualGateLockInRecipe.model_validate(dual_gate_lockin_recipe_data(tmp_path))
    safety = load_named_safety_preset(recipe.safety_preset)
    gate1_smu, gate2_smu, lockin = build_fake_dual_gate_lockin()
    metadata = run_dual_gate_lockin_sweep(recipe, safety, gate1_smu, gate2_smu, lockin)
    run_dir = Path(metadata["run_dir"])
    metadata_path = run_dir / "metadata.json"
    saved_metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    saved_metadata["output_state"]["gate1"]["off_after_run"] = False
    metadata_path.write_text(json.dumps(saved_metadata, indent=2, sort_keys=True), encoding="utf-8")

    acceptance = audit_dual_gate_lockin_run(run_dir, require_lockin_settings=False)

    assert acceptance.accepted is False
    assert any(issue.check == "gate1_output" for issue in acceptance.issues)


def test_dual_gate_lockin_acceptance_fails_grid_signature_mismatch(tmp_path):
    recipe = DualGateLockInRecipe.model_validate(dual_gate_lockin_recipe_data(tmp_path))
    safety = load_named_safety_preset(recipe.safety_preset)
    gate1_smu, gate2_smu, lockin = build_fake_dual_gate_lockin()
    metadata = run_dual_gate_lockin_sweep(recipe, safety, gate1_smu, gate2_smu, lockin)
    run_dir = Path(metadata["run_dir"])
    metadata_path = run_dir / "metadata.json"
    saved_metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    saved_metadata["planned_gate_grid"][0]["gate1_voltage_v"] = 0.123
    metadata_path.write_text(json.dumps(saved_metadata, indent=2, sort_keys=True), encoding="utf-8")

    acceptance = audit_dual_gate_lockin_run(run_dir, require_lockin_settings=False)

    assert acceptance.accepted is False
    assert any(issue.check == "planned_gate_grid" for issue in acceptance.issues)


def test_dual_gate_lockin_acceptance_warns_when_leakage_margin_is_small(tmp_path):
    recipe = DualGateLockInRecipe.model_validate(dual_gate_lockin_recipe_data(tmp_path))
    safety = load_named_safety_preset(recipe.safety_preset)
    gate1_smu, gate2_smu, lockin = build_fake_dual_gate_lockin()
    metadata = run_dual_gate_lockin_sweep(recipe, safety, gate1_smu, gate2_smu, lockin)
    run_dir = Path(metadata["run_dir"])
    csv_path = run_dir / "points.csv"
    rows = list(csv.DictReader(csv_path.open(newline="", encoding="utf-8")))
    for row in rows:
        row["gate1_current_a"] = "2e-9"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    acceptance = audit_dual_gate_lockin_run(run_dir, require_lockin_settings=False)

    assert acceptance.accepted is True
    assert acceptance.gate1_leakage_compliance_margin == pytest.approx(5)
    assert any(issue.check == "gate1_leakage_margin" and issue.severity == "warning" for issue in acceptance.issues)


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
    assert metadata["abort_class"] == "safety_stop"
    assert metadata["planned_points"] == 9
    assert metadata["points_written"] == 0
    assert metadata["remaining_points"] == 9
    assert metadata["last_completed_index"] is None
    assert metadata["next_point_index"] == 0
    assert metadata["recovery_recommendation"] == "do_not_resume_until_limit_cause_is_reviewed"
    assert metadata["outputs_off_after_run"] is True
    assert gate1_smu.is_output_on is False
    assert gate2_smu.is_output_on is False


def test_dual_gate_lockin_active_gate_smoke_writes_readout_and_turns_outputs_off(tmp_path):
    recipe = DualGateLockInRecipe.model_validate(dual_gate_lockin_recipe_data(tmp_path))
    safety = load_named_safety_preset(recipe.safety_preset)
    gate1_smu, gate2_smu, lockin = build_fake_dual_gate_lockin()

    metadata = run_dual_gate_lockin_active_gate_smoke(
        recipe,
        safety,
        gate1_smu,
        gate2_smu,
        lockin,
        gate1_voltage_v=0.01,
        gate2_voltage_v=-0.01,
        samples=3,
        interval_s=0,
        settle_s=0,
        recipe_path="active_smoke.yaml",
    )

    assert metadata["completed"] is True
    assert metadata["measurement_type"] == "dual_gate_lockin_active_gate_smoke"
    assert metadata["points_written"] == 3
    assert metadata["gate_outputs_enabled"] is False
    assert metadata["outputs_off_after_run"] is True
    assert gate1_smu.is_output_on is False
    assert gate2_smu.is_output_on is False
    rows = list(csv.DictReader((Path(metadata["run_dir"]) / "active_gate_smoke.csv").open(newline="", encoding="utf-8")))
    assert len(rows) == 3
    assert float(rows[0]["gate1_voltage_v"]) == pytest.approx(0.01)
    saved_metadata = json.loads(Path(metadata["metadata_path"]).read_text(encoding="utf-8"))
    assert saved_metadata["configured_gate1_smu"]["current_compliance_a"] == pytest.approx(1e-8)
    assert saved_metadata["configured_gate2_smu"]["current_range_a"] == pytest.approx(1e-9)
    assert saved_metadata["configured_gate1_smu_readback"]["source_function"] == "VOLT"
    assert saved_metadata["configured_gate2_smu_readback"]["current_range"] == "1e-09"
    assert saved_metadata["output_state"]["gate1"]["off_after_run"] is True
    assert saved_metadata["output_state"]["gate2"]["off_after_run"] is True


def test_dual_gate_lockin_active_gate_smoke_compliance_stop_turns_outputs_off(tmp_path):
    data = dual_gate_lockin_recipe_data(tmp_path)
    data["gate1_sweep"]["current_compliance_a"] = 1e-9
    recipe = DualGateLockInRecipe.model_validate(data)
    safety = load_named_safety_preset(recipe.safety_preset)
    state = DualGateFakeDeviceState(gate1_leak_resistance_ohm=1_000_000.0)
    gate1_smu = DualGateFakeSMU("gate1", state)
    gate2_smu = DualGateFakeSMU("gate2", state)
    lockin = DualGateFakeLockIn(state, base_r_v=1e-6, noise_std_v=0)

    metadata = run_dual_gate_lockin_active_gate_smoke(
        recipe,
        safety,
        gate1_smu,
        gate2_smu,
        lockin,
        gate1_voltage_v=0.01,
        gate2_voltage_v=0.0,
        samples=3,
        interval_s=0,
        settle_s=0,
    )

    assert metadata["completed"] is False
    assert metadata["error_type"] == "SafetyLimitError"
    assert metadata["triggered_limit"] == "gate1_instrument_compliance"
    assert metadata["gate_outputs_enabled"] is False
    assert metadata["outputs_off_after_run"] is True
    assert gate1_smu.is_output_on is False
    assert gate2_smu.is_output_on is False
