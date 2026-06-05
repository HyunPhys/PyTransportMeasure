import csv
import json
from pathlib import Path

import pytest

from pytransport.instruments.fake import FakeSMU
from pytransport.pulse import format_pulse_plan, pulse_point_count, run_pulse_measurement
from pytransport.pulse_review import (
    format_pulse_summary,
    summarize_pulse_run,
    write_pulse_plot_svg,
    write_pulse_report,
)
from pytransport.recipes import PulseRecipe, load_named_safety_preset, load_pulse_recipe


def pulse_recipe_data(output_dir: Path) -> dict:
    return {
        "measurement_name": "pulse_test",
        "safety_preset": "nano_device_safe",
        "experiment": {"sample_id": "sim", "device_id": "pulse_dev", "tags": ["pulse"]},
        "source_instrument": {
            "id": "keithley_2450",
            "address": "GPIB0::2::INSTR",
            "voltage_range_v": 0.2,
            "current_range_a": 1e-6,
        },
        "pulse": {
            "base_v": 0.0,
            "amplitude_v": 0.1,
            "width_s": 0.001,
            "period_s": 0.01,
            "count": 5,
            "current_compliance_a": 1e-6,
            "acquisition": "pulse_end",
        },
        "pulse_limits": {
            "max_abs_pulse_v": 0.2,
            "max_pulse_width_s": 0.01,
            "max_duty_cycle": 0.2,
            "max_pulse_count": 100,
            "max_total_on_time_s": 0.1,
        },
        "output": {"directory": output_dir},
        "checks": {"require_completed": True, "min_points": 5},
    }


def test_pulse_recipe_sample_and_plan():
    recipe = load_pulse_recipe("configs/recipes/pulse_dry_run.yaml")
    safety = load_named_safety_preset(recipe.safety_preset)
    plan = format_pulse_plan(recipe, safety, "configs/recipes/pulse_dry_run.yaml")

    assert recipe.measurement_name == "pulse_dry_run"
    assert pulse_point_count(recipe) == 5
    assert "Pulse Measurement Plan" in plan
    assert "Measurement geometry: two_terminal, 2-terminal" in plan
    assert "Total on-time: 0.005 s" in plan


def test_pulse_dry_run_writes_points_metadata_and_artifacts(tmp_path):
    recipe = PulseRecipe.model_validate(pulse_recipe_data(tmp_path))
    safety = load_named_safety_preset(recipe.safety_preset)
    source = FakeSMU(resistance_ohm=1_000_000, noise_std_a=0)

    metadata = run_pulse_measurement(recipe, safety, source, recipe_path="pulse.yaml")

    assert metadata["completed"] is True
    assert metadata["measurement_type"] == "pulse_measurement"
    assert metadata["points_written"] == 5
    assert source.is_output_on is False
    assert source.connected is False
    run_dir = Path(metadata["run_dir"])
    rows = list(csv.DictReader((run_dir / "points.csv").open(newline="", encoding="utf-8")))
    saved_metadata = json.loads((run_dir / "metadata.json").read_text(encoding="utf-8"))
    assert len(rows) == 5
    assert float(rows[0]["pulse_voltage_v"]) == pytest.approx(0.1)
    assert float(rows[0]["source_current_a"]) == pytest.approx(1e-7)
    assert saved_metadata["source_instrument_probe"]["idn"] == "FAKE,SMU,DRY-RUN,0"

    summary = summarize_pulse_run(run_dir)
    assert summary.points == 5
    assert summary.current_max_a == pytest.approx(1e-7)
    assert "Pulse run:" in format_pulse_summary(summary)
    assert write_pulse_plot_svg(run_dir).name == "pulse_plot.svg"
    assert write_pulse_report(run_dir).name == "pulse_report.md"


def test_pulse_compliance_stop_saves_partial_and_turns_off(tmp_path):
    recipe = PulseRecipe.model_validate(pulse_recipe_data(tmp_path))
    safety = load_named_safety_preset(recipe.safety_preset)
    source = FakeSMU(resistance_ohm=10_000, noise_std_a=0)

    metadata = run_pulse_measurement(recipe, safety, source)

    assert metadata["completed"] is False
    assert metadata["error_type"] == "SafetyLimitError"
    assert metadata["triggered_limit"] == "pulse_source_compliance"
    assert source.is_output_on is False
    assert source.connected is False


def test_pulse_recipe_rejects_unsafe_duty_cycle(tmp_path):
    data = pulse_recipe_data(tmp_path)
    data["pulse"]["width_s"] = 0.009
    data["pulse_limits"]["max_duty_cycle"] = 0.2

    with pytest.raises(Exception, match="pulse duty cycle"):
        PulseRecipe.model_validate(data)
