import csv
import json

from pytransport.plot import write_iv_svg


def test_write_iv_svg(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "metadata.json").write_text(
        json.dumps({"completed": True, "error_type": None, "error_message": None}),
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
                    "resistance_ohm": 1000.0,
                    "compliance_hit": False,
                }
            )

    output = write_iv_svg(run_dir)

    assert output == run_dir / "iv_plot.svg"
    text = output.read_text(encoding="utf-8")
    assert "<svg" in text
    assert 'height="560"' in text
    assert 'y="92"' in text
    assert "fitted R=1000 ohm" in text
