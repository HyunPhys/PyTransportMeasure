import csv
import json

from pytransport.summary import format_summary, summarize_run


def test_summarize_run_fits_resistance(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    with (run_dir / "metadata.json").open("w", encoding="utf-8") as handle:
        json.dump({"completed": True, "error_type": None, "error_message": None}, handle)
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
            current = voltage / 1000.0
            writer.writerow(
                {
                    "index": index,
                    "voltage_v": voltage,
                    "current_a": current,
                    "elapsed_s": index,
                    "resistance_ohm": 1000.0,
                    "compliance_hit": False,
                }
            )

    summary = summarize_run(run_dir)

    assert summary.completed is True
    assert summary.points == 3
    assert abs(summary.fitted_resistance_ohm - 1000.0) < 1e-9
    assert "Fitted resistance: 1000 ohm" in format_summary(summary)
