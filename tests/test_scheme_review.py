import csv
import json

import pytest

from pytransport.scheme_review import (
    evaluate_scheme_quality,
    summarize_scheme,
    update_scheme_summary_quality,
    write_scheme_overlay_svg,
    write_scheme_points_csv,
    write_scheme_report,
    write_scheme_runs_csv,
    write_scheme_stats_csv,
)


def write_run(run_dir, name, points):
    run_dir.mkdir(parents=True)
    with (run_dir / "metadata.json").open("w", encoding="utf-8") as handle:
        json.dump(
            {
                "measurement_name": name,
                "completed": True,
                "error_type": None,
                "error_message": None,
                "recipe": {"checks": {"require_completed": True}},
            },
            handle,
        )
    with (run_dir / "points.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["index", "voltage_v", "current_a", "elapsed_s", "resistance_ohm", "compliance_hit"],
        )
        writer.writeheader()
        for index, (voltage, current) in enumerate(points):
            writer.writerow(
                {
                    "index": index,
                    "voltage_v": voltage,
                    "current_a": current,
                    "elapsed_s": index * 0.1,
                    "resistance_ohm": None if current == 0 else voltage / current,
                    "compliance_hit": False,
                }
            )


def write_single_gate_run(run_dir, name):
    run_dir.mkdir(parents=True)
    with (run_dir / "metadata.json").open("w", encoding="utf-8") as handle:
        json.dump(
            {
                "measurement_name": name,
                "measurement_type": "single_gate_sweep",
                "completed": True,
                "error_type": None,
                "error_message": None,
                "recipe": {"experiment": {"sample_id": "sample", "device_id": "fet"}},
            },
            handle,
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
                        "elapsed_s": index * 0.1,
                        "drain_resistance_ohm": "" if drain_voltage == 0 else 1_000_000,
                        "drain_compliance_hit": False,
                        "gate_compliance_hit": False,
                    }
                )
                index += 1


def write_scheme_summary(tmp_path):
    run_a = tmp_path / "raw" / "run_a"
    run_b = tmp_path / "raw" / "run_b"
    write_run(run_a, "a", [(-0.1, -1e-4), (0.0, 0.0), (0.1, 1e-4)])
    write_run(run_b, "b", [(-0.05, -5e-5), (0.0, 0.0), (0.05, 5e-5)])
    scheme_dir = tmp_path / "scheme"
    scheme_dir.mkdir()
    summary_path = scheme_dir / "scheme_summary.json"
    summary_path.write_text(
        json.dumps(
            {
                "scheme_name": "test_scheme",
                "scheme_path": "scheme.yaml",
                "started_at": "start",
                "finished_at": "finish",
                "dry_run": True,
                "completed": True,
                "quality": None,
                "steps": [
                    {
                        "label": "a",
                        "type": "drain_iv",
                        "completed": True,
                        "error_type": None,
                        "run_dir": str(run_a),
                        "metadata_path": str(run_a / "metadata.json"),
                        "quality": {"status": "PASS", "results": []},
                    },
                    {
                        "label": "b",
                        "type": "drain_iv",
                        "completed": True,
                        "error_type": None,
                        "run_dir": str(run_b),
                        "metadata_path": str(run_b / "metadata.json"),
                        "quality": {"status": "PASS", "results": []},
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    return summary_path


def test_summarize_scheme_and_quality(tmp_path):
    summary_path = write_scheme_summary(tmp_path)

    review = summarize_scheme(summary_path)
    quality = evaluate_scheme_quality(summary_path)
    update_scheme_summary_quality(summary_path, quality)

    assert review.scheme_name == "test_scheme"
    assert len(review.runs) == 2
    assert review.runs[0].summary.fitted_resistance_ohm == pytest.approx(1000)
    assert quality["status"] == "PASS"
    saved = json.loads(summary_path.read_text(encoding="utf-8"))
    assert saved["quality"]["status"] == "PASS"


def test_write_scheme_review_artifacts(tmp_path):
    summary_path = write_scheme_summary(tmp_path)
    update_scheme_summary_quality(summary_path, evaluate_scheme_quality(summary_path))

    report = write_scheme_report(summary_path)
    runs = write_scheme_runs_csv(summary_path)
    points = write_scheme_points_csv(summary_path)
    stats = write_scheme_stats_csv(summary_path)
    plot = write_scheme_overlay_svg(summary_path)

    assert report.exists()
    assert "Scheme QC: PASS" in report.read_text(encoding="utf-8")
    assert runs.exists()
    assert points.exists()
    assert stats.exists()
    assert plot.exists()
    assert "test_scheme" in plot.read_text(encoding="utf-8")


def test_scheme_review_handles_single_gate_steps(tmp_path):
    run_dir = tmp_path / "raw" / "single_gate"
    write_single_gate_run(run_dir, "single_gate")
    scheme_dir = tmp_path / "scheme"
    scheme_dir.mkdir()
    summary_path = scheme_dir / "scheme_summary.json"
    summary_path.write_text(
        json.dumps(
            {
                "scheme_name": "mixed_scheme",
                "scheme_path": "scheme.yaml",
                "started_at": "start",
                "finished_at": "finish",
                "dry_run": True,
                "completed": True,
                "quality": None,
                "steps": [
                    {
                        "label": "gate",
                        "type": "single_gate",
                        "completed": True,
                        "error_type": None,
                        "run_dir": str(run_dir),
                        "metadata_path": str(run_dir / "metadata.json"),
                        "quality": None,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    review = summarize_scheme(summary_path)
    report = write_scheme_report(summary_path)
    runs = write_scheme_runs_csv(summary_path)
    points = write_scheme_points_csv(summary_path)

    assert review.runs[0].type == "single_gate"
    assert review.runs[0].summary.gate_points == 2
    assert "Gate leakage max" in report.read_text(encoding="utf-8")
    assert "gate_points" in runs.read_text(encoding="utf-8")
    assert "gate_voltage_v" in points.read_text(encoding="utf-8")
