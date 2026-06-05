import json
from pathlib import Path

from pytransport import cli
from pytransport.recipe_parameter_audit import (
    audit_recipe_parameter_directory,
    format_recipe_parameter_directory_audit,
    infer_measurement_type_from_yaml,
)
from pytransport.templates import write_recipe_template


def test_infer_measurement_type_from_recipe_shapes(tmp_path: Path):
    drain = write_recipe_template(
        tmp_path / "drain.yaml",
        mode="linear_one_way",
        measurement_name="drain",
        address="GPIB0::2::INSTR",
    )
    ac = tmp_path / "ac.yaml"
    ac.write_text(
        """
measurement_name: ac
source_instrument:
  id: keithley_2450
  address: GPIB0::2::INSTR
  voltage_range_v: 0.1
  current_range_a: 1.0e-7
  nplc: 1.0
lockin:
  enabled: true
  address: GPIB0::4::INSTR
bias_sweep:
  start_v: -0.001
  stop_v: 0.001
  points: 3
  delay_s: 0
  current_compliance_a: 1.0e-7
output:
  directory: data/raw
""".strip(),
        encoding="utf-8",
    )

    assert infer_measurement_type_from_yaml(drain) == "drain_iv"
    assert infer_measurement_type_from_yaml(ac) == "ac_lockin_sweep"


def test_recipe_parameter_directory_audit_reports_missing_nplc(tmp_path: Path):
    complete = write_recipe_template(
        tmp_path / "complete.yaml",
        mode="linear_one_way",
        measurement_name="complete",
        address="GPIB0::2::INSTR",
    )
    missing = tmp_path / "missing.yaml"
    text = complete.read_text(encoding="utf-8").replace("  nplc: 1.0\n", "")
    missing.write_text(text.replace("measurement_name: complete", "measurement_name: missing"), encoding="utf-8")

    payload = audit_recipe_parameter_directory(tmp_path)
    report = format_recipe_parameter_directory_audit(payload)

    assert payload["recipe_count"] == 2
    assert payload["ok_for_hardware"] is False
    assert payload["recipes"][0]["ok_for_hardware"] is True
    assert payload["recipes"][1]["ok_for_hardware"] is False
    assert "missing nplc" in report
    assert "Recipe measurement parameter directory audit" in report


def test_cli_measurement_parameter_audit_dir_writes_json(tmp_path: Path):
    write_recipe_template(
        tmp_path / "complete.yaml",
        mode="linear_one_way",
        measurement_name="complete",
        address="GPIB0::2::INSTR",
    )
    output = tmp_path / "audit.json"

    code = cli.main(["measurement-parameter-audit-dir", str(tmp_path), "--json-output", str(output)])

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert code == 0
    assert payload["ok_for_hardware"] is True
    assert payload["recipes"][0]["measurement_type"] == "drain_iv"
