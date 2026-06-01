from pathlib import Path

import pytest

from pytransport.errors import SafetyLimitError
from pytransport.validation import format_validation_report, validate_recipe_file


def test_validate_recipe_file_reports_smoke_test():
    report = validate_recipe_file(Path("configs/recipes/drain_iv_1k_resistor.yaml"))

    assert report.measurement_name == "drain_iv_1k_resistor_check"
    assert report.sample_id == "resistor_box"
    assert report.device_id == "1k_resistor"
    assert report.tags == ["smoke-test", "resistor"]
    assert report.points == 21
    assert report.estimated_duration_s == pytest.approx(1.05)
    assert report.terminal == "FRONT"
    assert "Recipe validation: OK" in format_validation_report(report)
    assert "Sample: resistor_box" in format_validation_report(report)


def test_validate_recipe_file_rejects_safety_limit(tmp_path):
    recipe_path = tmp_path / "unsafe.yaml"
    recipe_path.write_text(
        """
measurement_name: unsafe
safety_preset: nano_device_safe
instrument:
  id: keithley_2450
  address: FAKE
sweep:
  mode: linear_one_way
  start_v: -2.0
  stop_v: 2.0
  points: 3
  delay_s: 0
  current_compliance_a: 1.0e-7
output:
  directory: data/raw
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(SafetyLimitError):
        validate_recipe_file(recipe_path)
