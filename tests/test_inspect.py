import csv
import json

from pytransport.inspect import inspect_run


def test_inspect_run_reports_metadata_summary_and_files(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "metadata.json").write_text(
        json.dumps(
            {
                "completed": True,
                "error_type": None,
                "error_message": None,
                "recipe_path": "recipe.yaml",
                "recipe": {
                    "safety_preset": "resistor_1k_check",
                    "experiment": {
                        "sample_id": "sample",
                        "device_id": "device",
                        "operator": "operator",
                        "notes": "note",
                        "tags": ["tag"],
                    },
                    "instrument": {
                        "id": "keithley_2450",
                        "address": "GPIB0::2::INSTR",
                        "terminal": "FRONT",
                    },
                    "sweep": {"mode": "linear_one_way", "start_v": -0.1, "stop_v": 0.1, "points": 3},
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
                "voltage_v",
                "current_a",
                "elapsed_s",
                "resistance_ohm",
                "compliance_hit",
            ],
        )
        writer.writeheader()
        for index, voltage in enumerate([-0.1, 0.0, 0.1]):
            writer.writerow(
                {
                    "index": index,
                    "voltage_v": voltage,
                    "current_a": voltage / 1000.0,
                    "elapsed_s": index,
                    "resistance_ohm": 1000,
                    "compliance_hit": False,
                }
            )
    (run_dir / "iv_plot.svg").write_text("<svg />", encoding="utf-8")
    (run_dir / "recipe_snapshot.yaml").write_text("measurement_name: test\n", encoding="utf-8")
    (run_dir / "safety_snapshot.yaml").write_text("name: safe\n", encoding="utf-8")
    (run_dir / "report.md").write_text("# report\n", encoding="utf-8")

    text = inspect_run(run_dir)

    assert "Run inspection" in text
    assert "Sample: sample" in text
    assert "Device: device" in text
    assert "Fitted resistance: 1000 ohm" in text
    assert "Sweep: linear_one_way, -0.1 V to 0.1 V, 3 base points" in text
    assert "iv_plot.svg: yes" in text
    assert "recipe_snapshot.yaml: yes" in text
    assert "safety_snapshot.yaml: yes" in text
    assert "report.md: yes" in text


def test_inspect_single_gate_run_reports_gate_summary_and_files(tmp_path):
    run_dir = tmp_path / "single_gate"
    run_dir.mkdir()
    (run_dir / "metadata.json").write_text(
        json.dumps(
            {
                "measurement_name": "single_gate",
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
    (run_dir / "single_gate_heatmap.svg").write_text("<svg />", encoding="utf-8")
    (run_dir / "single_gate_stats.csv").write_text("gate_index\n0\n", encoding="utf-8")
    (run_dir / "single_gate_report.md").write_text("# report\n", encoding="utf-8")

    text = inspect_run(run_dir)

    assert "Measurement type: single_gate_sweep" in text
    assert "Gate points: 2" in text
    assert "Drain points per gate: 3" in text
    assert "Gate instrument: keithley_2450 @ GPIB0::3::INSTR" in text
    assert "single_gate_heatmap.svg: yes" in text
