import json
from pathlib import Path

from pytransport import cli


def write_dual_gate_lockin_recipe(
    tmp_path: Path,
    *,
    include_gate2_nplc: bool = True,
    complete_lockin_settings: bool = False,
) -> Path:
    recipe = tmp_path / "dual_gate_lockin.yaml"
    gate2_nplc = "  nplc: 1.0\n" if include_gate2_nplc else ""
    lockin_settings = """
  reference_source: internal
  reference_frequency_hz: 17.777
  sine_output_amplitude_v: 0.01
  input_mode: voltage
  voltage_input: a-b
  input_coupling: ac
  input_grounding: float
  voltage_input_range_v: 0.01
  sensitivity_index: 18
  time_constant_index: 10
  settle_time_constants: 3.0
  filter_slope_db_per_oct: 24
  synchronous_filter: false
""" if complete_lockin_settings else ""
    output_dir = str(tmp_path / "raw").replace("\\", "/")
    recipe.write_text(
        f"""
measurement_name: cli_audit_dual_gate_lockin
safety_preset: nano_device_safe
gate1_instrument:
  id: keithley_2450
  address: GPIB0::2::INSTR
  terminal: FRONT
  voltage_range_v: 0.2
  current_range_a: 1.0e-9
  nplc: 1.0
  source_delay_s: 0.05
gate2_instrument:
  id: keithley_2450
  address: GPIB0::3::INSTR
  terminal: FRONT
  voltage_range_v: 0.2
  current_range_a: 1.0e-9
{gate2_nplc}lockin:
  enabled: true
  id: srs_sr860
  address: GPIB0::4::INSTR
  channels: [x, y, r, theta]
{lockin_settings.rstrip()}
topology:
  source_contact: S
  drain_contact: D
  lockin_input_contacts: [V1, V2]
  excitation_contacts: [S, D]
  excitation_amplitude_v: 0.01
gate1_sweep:
  start_v: -0.1
  stop_v: 0.1
  points: 3
  settle_s: 0
  current_compliance_a: 1.0e-9
gate2_sweep:
  start_v: -0.1
  stop_v: 0.1
  points: 3
  settle_s: 0
  current_compliance_a: 1.0e-9
output:
  directory: {output_dir}
""".strip(),
        encoding="utf-8",
    )
    return recipe


def test_cli_keithley_parameter_audit_writes_json_for_complete_recipe(tmp_path):
    recipe = write_dual_gate_lockin_recipe(tmp_path)
    output = tmp_path / "audit.json"

    code = cli.main(["keithley-parameter-audit", "dual_gate_lockin_sweep", str(recipe), "--json-output", str(output)])

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert code == 0
    assert payload["ok_for_hardware"] is True
    assert payload["measurement_type"] == "dual_gate_lockin_sweep"
    assert [role["role"] for role in payload["roles"]] == ["gate1", "gate2"]
    assert payload["roles"][0]["nplc"] == 1.0


def test_cli_keithley_parameter_audit_returns_nonzero_for_missing_nplc(tmp_path):
    recipe = write_dual_gate_lockin_recipe(tmp_path, include_gate2_nplc=False)
    output = tmp_path / "audit.json"

    code = cli.main(["keithley-parameter-audit", "dual_gate_lockin_sweep", str(recipe), "--json-output", str(output)])

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert code == 2
    assert payload["ok_for_hardware"] is False
    assert payload["roles"][1]["missing_required_parameters"] == ["nplc"]


def test_cli_measurement_parameter_audit_writes_combined_json_for_complete_recipe(tmp_path):
    recipe = write_dual_gate_lockin_recipe(tmp_path, complete_lockin_settings=True)
    output = tmp_path / "measurement_audit.json"

    code = cli.main(["measurement-parameter-audit", "dual_gate_lockin_sweep", str(recipe), "--json-output", str(output)])

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert code == 0
    assert payload["ok_for_hardware"] is True
    assert payload["smu"]["ok_for_hardware"] is True
    assert payload["lockin"]["ok_for_hardware"] is True
    assert payload["lockin"]["roles"][0]["sensitivity_index"] == 18
    assert payload["lockin"]["roles"][0]["settle_policy_ok"] is True


def test_cli_measurement_parameter_audit_returns_nonzero_for_missing_lockin_conditions(tmp_path):
    recipe = write_dual_gate_lockin_recipe(tmp_path)
    output = tmp_path / "measurement_audit.json"

    code = cli.main(["measurement-parameter-audit", "dual_gate_lockin_sweep", str(recipe), "--json-output", str(output)])

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert code == 2
    assert payload["smu"]["ok_for_hardware"] is True
    assert payload["lockin"]["ok_for_hardware"] is False
    assert "sensitivity_index" in payload["lockin"]["roles"][0]["missing_required_parameters"]


def test_cli_measurement_parameter_audit_dir_returns_nonzero_for_missing_nplc(tmp_path):
    complete = write_dual_gate_lockin_recipe(tmp_path, complete_lockin_settings=True)
    missing = tmp_path / "missing_nplc.yaml"
    missing.write_text(
        complete.read_text(encoding="utf-8")
        .replace("measurement_name: cli_audit_dual_gate_lockin", "measurement_name: missing_nplc")
        .replace("  nplc: 1.0\n", "", 1),
        encoding="utf-8",
    )
    output = tmp_path / "dir_audit.json"

    code = cli.main(["measurement-parameter-audit-dir", str(tmp_path), "--json-output", str(output)])

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert code == 2
    assert payload["recipe_count"] == 2
    assert payload["ok_for_hardware"] is False
    assert any(
        "nplc" in role["missing_required_parameters"]
        for record in payload["recipes"]
        if record["loaded"]
        for role in record["audit"]["smu"]["roles"]
    )
