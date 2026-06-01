import argparse
import csv
import json

from pytransport.cli import command_plot, command_report, command_summarize
from pytransport.method_registry import (
    handler_for_measurement_type,
    handler_for_scheme_step,
    known_measurement_types,
    measurement_type_from_metadata,
)


def write_single_gate_run(run_dir):
    run_dir.mkdir()
    (run_dir / "metadata.json").write_text(
        json.dumps(
            {
                "measurement_name": "single_gate_registry",
                "measurement_type": "single_gate_sweep",
                "completed": True,
                "error_type": None,
                "error_message": None,
                "recipe_path": "single_gate.yaml",
                "recipe": {
                    "safety_preset": "nano_device_safe",
                    "experiment": {"sample_id": "sample", "device_id": "fet", "tags": ["gate"]},
                    "drain_instrument": {"id": "keithley_2450", "address": "GPIB0::2::INSTR"},
                    "gate_instrument": {"id": "keithley_2450", "address": "GPIB0::3::INSTR"},
                    "drain_sweep": {"mode": "linear_one_way", "start_v": -0.1, "stop_v": 0.1, "points": 3},
                    "gate_sweep": {"start_v": -0.5, "stop_v": 0.5, "points": 2, "settle_s": 0.0},
                },
            }
        ),
        encoding="utf-8",
    )
    with (run_dir / "points.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "index",
                "gate_index",
                "drain_index",
                "gate_voltage_v",
                "drain_voltage_v",
                "drain_current_a",
                "gate_current_a",
                "elapsed_s",
                "drain_resistance_ohm",
                "drain_compliance_hit",
                "gate_compliance_hit",
            ],
        )
        writer.writeheader()
        index = 0
        for gate_index, gate_voltage in enumerate([-0.5, 0.5]):
            for drain_index, drain_voltage in enumerate([-0.1, 0.0, 0.1]):
                writer.writerow(
                    {
                        "index": index,
                        "gate_index": gate_index,
                        "drain_index": drain_index,
                        "gate_voltage_v": gate_voltage,
                        "drain_voltage_v": drain_voltage,
                        "drain_current_a": drain_voltage / 1_000_000,
                        "gate_current_a": gate_voltage / 1_000_000_000,
                        "elapsed_s": index,
                        "drain_resistance_ohm": "" if drain_voltage == 0 else 1_000_000,
                        "drain_compliance_hit": False,
                        "gate_compliance_hit": False,
                    }
                )
                index += 1


def test_registry_lists_known_measurement_types_and_defaults_legacy_metadata():
    assert known_measurement_types() == ("drain_iv", "single_gate_sweep", "ac_lockin_sweep", "pulse_measurement")
    assert measurement_type_from_metadata({}) == "drain_iv"
    assert handler_for_measurement_type("drain_iv").scheme_step_type == "drain_iv"
    assert handler_for_scheme_step("single_gate").measurement_type == "single_gate_sweep"
    assert handler_for_scheme_step("ac_lockin").measurement_type == "ac_lockin_sweep"
    assert handler_for_scheme_step("pulse").measurement_type == "pulse_measurement"


def test_registry_loads_and_formats_method_plans():
    drain = handler_for_measurement_type("drain_iv")
    drain_recipe_path = "configs/recipes/drain_iv_1k_resistor.yaml"
    drain_recipe = drain.load_recipe(drain_recipe_path)
    drain_plan = drain.format_plan(drain_recipe, drain_recipe_path, "configs/safety", 3)

    assert "Measurement plan" in drain_plan
    assert "drain_iv_1k_resistor_check" in drain_plan

    single_gate = handler_for_measurement_type("single_gate_sweep")
    single_gate_recipe_path = "configs/recipes/single_gate_dry_run.yaml"
    single_gate_recipe = single_gate.load_recipe(single_gate_recipe_path)
    single_gate_plan = single_gate.format_plan(single_gate_recipe, single_gate_recipe_path, "configs/safety", 3)

    assert "Single-Gate Sweep Plan" in single_gate_plan
    assert "single_gate_dry_run" in single_gate_plan

    ac_lockin = handler_for_measurement_type("ac_lockin_sweep")
    ac_lockin_recipe_path = "configs/recipes/ac_lockin_dry_run.yaml"
    ac_lockin_recipe = ac_lockin.load_recipe(ac_lockin_recipe_path)
    ac_lockin_plan = ac_lockin.format_plan(ac_lockin_recipe, ac_lockin_recipe_path, "configs/safety", 3)

    assert "AC Lock-In Sweep Plan" in ac_lockin_plan
    assert "ac_lockin_dry_run" in ac_lockin_plan

    pulse = handler_for_measurement_type("pulse_measurement")
    pulse_recipe_path = "configs/recipes/pulse_dry_run.yaml"
    pulse_recipe = pulse.load_recipe(pulse_recipe_path)
    pulse_plan = pulse.format_plan(pulse_recipe, pulse_recipe_path, "configs/safety", 3)

    assert "Pulse Measurement Plan" in pulse_plan
    assert "pulse_dry_run" in pulse_plan


def test_generic_saved_run_commands_dispatch_single_gate(tmp_path, capsys):
    run_dir = tmp_path / "single_gate"
    write_single_gate_run(run_dir)

    assert command_summarize(argparse.Namespace(run_dir=run_dir)) == 0
    text = capsys.readouterr().out
    assert "Single-gate run:" in text
    assert "Gate points: 2" in text

    assert command_plot(argparse.Namespace(run_dir=run_dir, output=None)) == 0
    assert (run_dir / "single_gate_heatmap.svg").exists()

    assert command_report(argparse.Namespace(run_dir=run_dir, output=None)) == 0
    assert (run_dir / "single_gate_report.md").exists()
