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
    assert report.nplc == 1.0
    assert report.measurement_geometry["terminal_count"] == 2
    assert "Recipe validation: OK" in format_validation_report(report)
    assert "Measurement geometry: two_terminal, 2-terminal" in format_validation_report(report)
    assert "NPLC: 1" in format_validation_report(report)
    assert "Sample: resistor_box" in format_validation_report(report)


def test_validate_recipe_file_reports_lab_context(tmp_path):
    recipe_path = tmp_path / "context.yaml"
    recipe_path.write_text(
        """
measurement_name: context
safety_preset: nano_device_safe
experiment:
  sample_id: sample-a
  device_id: dev-1
  cooldown_id: cd-1
  contact_geometry: hall bar
  lab_notebook_ref: ELN-1
instrument:
  id: keithley_2450
  address: FAKE
sweep:
  mode: linear_one_way
  start_v: -0.01
  stop_v: 0.01
  points: 3
  delay_s: 0
  current_compliance_a: 1.0e-7
output:
  directory: data/raw
""".strip(),
        encoding="utf-8",
    )

    report = validate_recipe_file(recipe_path)
    text = format_validation_report(report)

    assert report.cooldown_id == "cd-1"
    assert "Contact geometry: hall bar" in text
    assert "Lab notebook: ELN-1" in text


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
