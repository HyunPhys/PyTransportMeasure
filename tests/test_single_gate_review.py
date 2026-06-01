import csv
import json
from pathlib import Path

import pytest

from pytransport.instruments.fake import CoupledFakeDeviceState, CoupledFakeSMU
from pytransport.recipes import SingleGateRecipe, load_named_safety_preset
from pytransport.single_gate import run_single_gate_sweep
from pytransport.single_gate_review import (
    format_single_gate_report,
    format_single_gate_summary,
    summarize_single_gate_run,
    write_single_gate_heatmap_svg,
    write_single_gate_report,
    write_single_gate_stats_csv,
)
from tests.test_single_gate import single_gate_recipe_data


def make_single_gate_run(tmp_path: Path) -> Path:
    recipe = SingleGateRecipe.model_validate(single_gate_recipe_data(tmp_path))
    safety = load_named_safety_preset(recipe.safety_preset)
    state = CoupledFakeDeviceState(
        channel_resistance_ohm=1_000_000.0,
        gate_leak_resistance_ohm=1_000_000_000.0,
        noise_std_a=0.0,
    )
    metadata = run_single_gate_sweep(
        recipe,
        safety,
        CoupledFakeSMU("drain", state),
        CoupledFakeSMU("gate", state),
    )
    return Path(metadata["run_dir"])


def test_single_gate_summary_and_format(tmp_path):
    run_dir = make_single_gate_run(tmp_path)

    summary = summarize_single_gate_run(run_dir)
    text = format_single_gate_summary(summary)

    assert summary.completed is True
    assert summary.points == 15
    assert summary.gate_points == 3
    assert summary.drain_points == 5
    assert summary.gate_leakage_abs_max_a == 5e-10
    assert "Single-gate run:" in text
    assert "Gate points: 3" in text


def test_single_gate_stats_heatmap_and_report(tmp_path):
    run_dir = make_single_gate_run(tmp_path)

    stats_path = write_single_gate_stats_csv(run_dir)
    heatmap_path = write_single_gate_heatmap_svg(run_dir)
    report_path = write_single_gate_report(run_dir)

    stats_rows = list(csv.DictReader(stats_path.open(newline="", encoding="utf-8")))
    report = report_path.read_text(encoding="utf-8")
    assert len(stats_rows) == 3
    assert float(stats_rows[0]["fitted_drain_resistance_ohm"]) == pytest.approx(1_000_000.0)
    assert heatmap_path.exists()
    assert "Drain voltage (V)" in heatmap_path.read_text(encoding="utf-8")
    assert "# single_gate_test" in report
    assert "## Gate Statistics" in report
    assert "![Single-gate heatmap](single_gate_heatmap.svg)" in report


def test_single_gate_report_without_heatmap_link_when_missing(tmp_path):
    run_dir = make_single_gate_run(tmp_path)

    report = format_single_gate_report(run_dir)

    assert "## Gate Statistics" in report
    assert "single_gate_heatmap.svg" not in report


def test_single_gate_metadata_can_record_review_paths(tmp_path):
    run_dir = make_single_gate_run(tmp_path)
    stats_path = write_single_gate_stats_csv(run_dir)
    heatmap_path = write_single_gate_heatmap_svg(run_dir)
    report_path = write_single_gate_report(run_dir)
    metadata_path = run_dir / "metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata.update(
        {
            "single_gate_stats_path": str(stats_path),
            "single_gate_heatmap_path": str(heatmap_path),
            "single_gate_report_path": str(report_path),
        }
    )
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    saved = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert saved["single_gate_stats_path"].endswith("single_gate_stats.csv")
    assert saved["single_gate_heatmap_path"].endswith("single_gate_heatmap.svg")
    assert saved["single_gate_report_path"].endswith("single_gate_report.md")
