import json

from pytransport.instruments.fake import FakeSMU
from pytransport.quality import evaluate_run_quality, format_quality_report
from pytransport.recipes import DrainIVRecipe, SafetyPreset
from pytransport.runner import run_drain_iv


def make_recipe(tmp_path, resistance_min=900, resistance_max=1100):
    return DrainIVRecipe.model_validate(
        {
            "measurement_name": "quality_test",
            "instrument": {"address": "FAKE"},
            "sweep": {
                "start_v": -0.1,
                "stop_v": 0.1,
                "points": 5,
                "delay_s": 0,
                "current_compliance_a": 1e-3,
            },
            "output": {"directory": str(tmp_path)},
            "checks": {
                "require_completed": True,
                "min_points": 5,
                "fitted_resistance_ohm": {
                    "min_ohm": resistance_min,
                    "max_ohm": resistance_max,
                },
            },
        }
    )


def make_safety():
    return SafetyPreset(
        name="resistor_test",
        max_abs_voltage_v=1.0,
        max_abs_current_a=1e-3,
        default_current_compliance_a=1e-3,
    )


def test_quality_passes_for_expected_resistance(tmp_path):
    metadata = run_drain_iv(make_recipe(tmp_path), make_safety(), FakeSMU(resistance_ohm=1000, noise_std_a=0))
    report = evaluate_run_quality(metadata["run_dir"])

    assert report.status == "PASS"
    assert "Quality: PASS" in format_quality_report(report)


def test_quality_fails_for_wrong_resistance(tmp_path):
    metadata = run_drain_iv(make_recipe(tmp_path), make_safety(), FakeSMU(resistance_ohm=10_000, noise_std_a=0))
    report = evaluate_run_quality(metadata["run_dir"])

    assert report.status == "FAIL"
    assert any(result.name == "fitted_resistance_ohm" and not result.passed for result in report.results)


def test_quality_is_written_to_metadata_by_cli_style_update(tmp_path):
    metadata = run_drain_iv(make_recipe(tmp_path), make_safety(), FakeSMU(resistance_ohm=1000, noise_std_a=0))
    report = evaluate_run_quality(metadata["run_dir"])
    metadata["quality"] = {"status": report.status}
    metadata_path = next(tmp_path.iterdir()) / "metadata.json"
    saved = json.loads(metadata_path.read_text(encoding="utf-8"))

    assert saved["recipe"]["checks"]["min_points"] == 5
    assert metadata["quality"]["status"] == "PASS"
