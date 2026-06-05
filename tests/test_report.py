import csv
import json

from pytransport.report import write_run_report


def test_write_run_report(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "metadata.json").write_text(
        json.dumps(
            {
                "measurement_name": "report_test",
                "started_at": "2026-05-26T16:00:00",
                "finished_at": "2026-05-26T16:00:01",
                "completed": True,
                "interrupted": False,
                "error_type": None,
                "error_message": None,
                "recipe_path": "recipe.yaml",
                "recipe": {
                    "safety_preset": "resistor_1k_check",
                    "experiment": {
                        "sample_id": "sample",
                        "device_id": "device",
                        "cooldown_id": "cooldown-1",
                        "contact_geometry": "hall bar",
                        "contact_notes": "outer pads",
                        "lab_notebook_ref": "ELN-1 p.2",
                        "operator": "operator",
                        "notes": "note",
                        "tags": ["tag"],
                    },
                    "instrument": {
                        "id": "keithley_2450",
                        "address": "GPIB0::2::INSTR",
                        "terminal": "FRONT",
                        "voltage_range_v": 0.2,
                        "current_range_a": 2e-4,
                    },
                    "sweep": {
                        "mode": "linear_one_way",
                        "start_v": -0.1,
                        "stop_v": 0.1,
                        "points": 3,
                        "current_compliance_a": 2e-4,
                    },
                },
                "safety": {
                    "name": "resistor_1k_check",
                    "max_abs_voltage_v": 0.2,
                    "max_abs_current_a": 5e-4,
                    "default_current_compliance_a": 2e-4,
                },
            }
        ),
        encoding="utf-8",
    )
    with (run_dir / "points.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["index", "voltage_v", "current_a", "elapsed_s", "resistance_ohm", "compliance_hit"],
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

    output = write_run_report(run_dir)

    text = output.read_text(encoding="utf-8")
    assert output == run_dir / "report.md"
    assert "# report_test" in text
    assert "- Sample: sample" in text
    assert "- Cooldown: cooldown-1" in text
    assert "- Contact geometry: hall bar" in text
    assert "- Lab notebook: ELN-1 p.2" in text
    assert "- Fitted resistance: 1000 ohm" in text
    assert "![I-V plot](iv_plot.svg)" in text
