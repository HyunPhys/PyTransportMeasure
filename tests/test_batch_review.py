import csv
import json
from pathlib import Path

import pytest

from pytransport.batch_review import (
    evaluate_batch_quality,
    format_batch_review,
    summarize_batch,
    update_batch_summary_quality,
    write_batch_overlay_svg,
    write_batch_points_csv,
    write_batch_report,
    write_batch_stats_csv,
)


def write_fake_run(run_dir: Path, name: str, resistance_ohm: float) -> None:
    run_dir.mkdir(parents=True)
    with (run_dir / "points.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["index", "voltage_v", "current_a", "elapsed_s", "resistance_ohm", "compliance_hit"],
        )
        writer.writeheader()
        for index, voltage in enumerate([-0.1, 0.0, 0.1]):
            current = voltage / resistance_ohm
            writer.writerow(
                {
                    "index": index,
                    "voltage_v": voltage,
                    "current_a": current,
                    "elapsed_s": index * 0.01,
                    "resistance_ohm": resistance_ohm if current else "",
                    "compliance_hit": False,
                }
            )
    metadata = {
        "measurement_name": name,
        "completed": True,
        "interrupted": False,
        "error_type": None,
        "error_message": None,
    }
    (run_dir / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")


def write_fake_batch(tmp_path: Path) -> Path:
    run_a = tmp_path / "run_a"
    run_b = tmp_path / "run_b"
    write_fake_run(run_a, "linear", 1000)
    write_fake_run(run_b, "repeat", 1005)
    batch_dir = tmp_path / "batch"
    batch_dir.mkdir()
    summary = {
        "batch_name": "fake_batch",
        "batch_path": "configs/batches/fake.yaml",
        "started_at": "2026-01-01T00:00:00",
        "finished_at": "2026-01-01T00:00:01",
        "dry_run": True,
        "completed": True,
        "checks": {
            "require_all_completed": True,
            "require_all_run_quality_pass": True,
            "max_relative_std_percent": 1.0,
        },
        "quality": None,
        "runs": [
            {
                "label": "linear",
                "base_label": "repeat_group",
                "repeat_index": 1,
                "repeat_count": 2,
                "recipe_path": "linear.yaml",
                "completed": True,
                "points_written": 3,
                "run_dir": str(run_a),
                "quality": {"status": "PASS", "results": []},
            },
            {
                "label": "repeat",
                "base_label": "repeat_group",
                "repeat_index": 2,
                "repeat_count": 2,
                "recipe_path": "repeat.yaml",
                "completed": True,
                "points_written": 3,
                "run_dir": str(run_b),
                "quality": {"status": "PASS", "results": []},
            },
        ],
    }
    summary_path = batch_dir / "batch_summary.json"
    summary_path.write_text(json.dumps(summary), encoding="utf-8")
    return summary_path


def test_summarize_batch_and_format(tmp_path):
    summary_path = write_fake_batch(tmp_path)

    review = summarize_batch(summary_path.parent)
    text = format_batch_review(review)

    assert review.batch_name == "fake_batch"
    assert len(review.runs) == 2
    assert review.runs[0].summary is not None
    assert review.runs[0].summary.fitted_resistance_ohm == pytest.approx(1000)
    assert "fitted R=1000 ohm" in text


def test_write_batch_report_and_overlay(tmp_path):
    summary_path = write_fake_batch(tmp_path)

    plot_path = write_batch_overlay_svg(summary_path)
    quality = evaluate_batch_quality(summary_path)
    update_batch_summary_quality(summary_path, quality)
    report_path = write_batch_report(summary_path)

    assert plot_path.exists()
    assert report_path.exists()
    assert quality["status"] == "PASS"
    assert "<polyline" in plot_path.read_text(encoding="utf-8")
    csv_path = report_path.with_name("batch_runs.csv")
    points_path = report_path.with_name("batch_points.csv")
    stats_path = report_path.with_name("batch_stats.csv")
    from pytransport.batch_review import write_batch_runs_csv

    write_batch_runs_csv(summary_path, csv_path)
    write_batch_points_csv(summary_path, points_path)
    write_batch_stats_csv(summary_path, stats_path)

    assert "| 1 | linear | 1/2 | True | PASS | 3 | 1000 ohm |" in report_path.read_text(encoding="utf-8")
    assert "## Stability Stats" in report_path.read_text(encoding="utf-8")
    assert "## Batch Quality" in report_path.read_text(encoding="utf-8")
    assert "repeat_index,repeat_count" in csv_path.read_text(encoding="utf-8")
    points_lines = points_path.read_text(encoding="utf-8").splitlines()
    assert points_lines[0].startswith("batch_index,label,base_label,repeat_index")
    assert len(points_lines) == 7
    assert ",linear,repeat_group,1,2," in points_lines[1]
    stats_text = stats_path.read_text(encoding="utf-8")
    assert "base_label,runs,completed,qc_pass,qc_fail" in stats_text
    assert "repeat_group,2,2,2,0" in stats_text


def test_batch_quality_fails_when_relative_std_exceeds_limit(tmp_path):
    summary_path = write_fake_batch(tmp_path)
    data = json.loads(summary_path.read_text(encoding="utf-8"))
    data["checks"]["max_relative_std_percent"] = 0.01
    summary_path.write_text(json.dumps(data), encoding="utf-8")

    quality = evaluate_batch_quality(summary_path)

    assert quality["status"] == "FAIL"
    assert any(result["name"] == "relative_std_percent:repeat_group" for result in quality["results"])
