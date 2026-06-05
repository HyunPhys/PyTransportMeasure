import csv
import json
from pathlib import Path

import pytest

from pytransport.cli import main
from pytransport.dual_gate_lockin import ELEMENTARY_CHARGE_C
from pytransport.hall_analysis import write_dual_gate_lockin_hall_antisym


def write_hall_run(run_dir: Path, field_t: float, x_values: list[float]) -> Path:
    run_dir.mkdir(parents=True)
    metadata = {
        "measurement_name": f"hall_{field_t:g}T",
        "measurement_type": "dual_gate_lockin_sweep",
        "completed": True,
        "voltage_probe_role": "hall",
        "magnetic_field_t": field_t,
        "points_written": len(x_values),
        "planned_points": len(x_values),
    }
    (run_dir / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    with (run_dir / "points.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "index",
                "gate1_index",
                "gate2_index",
                "gate1_voltage_v",
                "gate2_voltage_v",
                "gate1_current_a",
                "gate2_current_a",
                "elapsed_s",
                "gate1_compliance_hit",
                "gate2_compliance_hit",
                "lockin_x_v",
                "lockin_y_v",
                "lockin_r_v",
                "lockin_theta_deg",
                "source_drain_nominal_current_a",
                "lockin_hall_resistance_ohm",
            ],
        )
        writer.writeheader()
        for index, x_value in enumerate(x_values):
            writer.writerow(
                {
                    "index": index,
                    "gate1_index": index,
                    "gate2_index": 0,
                    "gate1_voltage_v": [-0.1, 0.0, 0.1][index],
                    "gate2_voltage_v": 0.0,
                    "gate1_current_a": 1e-12,
                    "gate2_current_a": 1e-12,
                    "elapsed_s": index,
                    "gate1_compliance_hit": "False",
                    "gate2_compliance_hit": "False",
                    "lockin_x_v": x_value,
                    "lockin_y_v": 0.0,
                    "lockin_r_v": abs(x_value),
                    "lockin_theta_deg": 0.0,
                    "source_drain_nominal_current_a": 1e-8,
                    "lockin_hall_resistance_ohm": "",
                }
            )
    return run_dir


def test_hall_antisym_writes_csv_report_and_metadata(tmp_path):
    positive = write_hall_run(tmp_path / "plus_b", 1.0, [2e-6, 3e-6, 4e-6])
    negative = write_hall_run(tmp_path / "minus_b", -1.0, [-1e-6, -2e-6, -3e-6])

    result = write_dual_gate_lockin_hall_antisym(positive, negative, tmp_path / "antisym")

    assert result.points == 3
    rows = list(csv.DictReader(result.output_csv.open(newline="", encoding="utf-8")))
    first_hall = float(rows[0]["hall_antisym_resistance_ohm"])
    assert first_hall == pytest.approx(0.5 * ((2e-6 / 1e-8) - (-1e-6 / 1e-8)))
    assert float(rows[0]["field_even_resistance_ohm"]) == pytest.approx(50.0)
    assert float(rows[0]["hall_carrier_density_per_m2"]) == pytest.approx(1.0 / (ELEMENTARY_CHARGE_C * first_hall))
    assert "Hall Antisymmetrization Report" in result.report_path.read_text(encoding="utf-8")
    metadata = json.loads(result.metadata_path.read_text(encoding="utf-8"))
    assert metadata["value_column"] == "lockin_x_v"
    assert metadata["points"] == 3


def test_hall_antisym_rejects_same_field_sign(tmp_path):
    positive = write_hall_run(tmp_path / "plus_b", 1.0, [2e-6, 3e-6, 4e-6])
    negative = write_hall_run(tmp_path / "not_minus_b", 1.0, [-1e-6, -2e-6, -3e-6])

    with pytest.raises(ValueError, match="negative_run"):
        write_dual_gate_lockin_hall_antisym(positive, negative, tmp_path / "antisym")


def test_cli_dual_gate_lockin_hall_antisym(tmp_path):
    positive = write_hall_run(tmp_path / "plus_b", 1.0, [2e-6, 3e-6, 4e-6])
    negative = write_hall_run(tmp_path / "minus_b", -1.0, [-1e-6, -2e-6, -3e-6])
    output = tmp_path / "cli_antisym"

    code = main(["dual-gate-lockin-hall-antisym", str(positive), str(negative), "--output-dir", str(output)])

    assert code == 0
    assert (output / "hall_antisym.csv").exists()
    assert (output / "hall_antisym_report.md").exists()
    assert (output / "hall_antisym_metadata.json").exists()

