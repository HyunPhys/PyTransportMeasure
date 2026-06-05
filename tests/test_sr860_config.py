import json
from pathlib import Path

from pytransport import cli
from pytransport.recipes import DualGateLockInRecipe
from pytransport.sr860_config import build_sr860_config_commands, review_sr860_config_commands


def dual_gate_lockin_recipe(tmp_path: Path, *, complete_lockin: bool = True) -> DualGateLockInRecipe:
    lockin = {
        "enabled": True,
        "id": "srs_sr860",
        "address": "GPIB0::4::INSTR",
        "channels": ["x", "y", "r", "theta"],
    }
    if complete_lockin:
        lockin.update(
            {
                "reference_source": "internal",
                "reference_frequency_hz": 17.777,
                "sine_output_amplitude_v": 0.01,
                "input_mode": "voltage",
                "voltage_input": "a-b",
                "input_coupling": "ac",
                "input_grounding": "float",
                "voltage_input_range_v": 0.01,
                "sensitivity_index": 18,
                "time_constant_index": 10,
                "settle_time_constants": 3.0,
                "filter_slope_db_per_oct": 24,
                "synchronous_filter": False,
            }
        )
    return DualGateLockInRecipe.model_validate(
        {
            "measurement_name": "sr860_review",
            "gate1_instrument": {
                "id": "keithley_2450",
                "address": "GPIB0::2::INSTR",
                "voltage_range_v": 0.2,
                "current_range_a": 1e-9,
                "nplc": 1.0,
            },
            "gate2_instrument": {
                "id": "keithley_2450",
                "address": "GPIB0::3::INSTR",
                "voltage_range_v": 0.2,
                "current_range_a": 1e-9,
                "nplc": 1.0,
            },
            "lockin": lockin,
            "topology": {
                "source_contact": "S",
                "drain_contact": "D",
                "lockin_input_contacts": ["V1", "V2"],
                "excitation_contacts": ["S", "D"],
                "excitation_amplitude_v": 0.01,
            },
            "gate1_sweep": {
                "start_v": -0.1,
                "stop_v": 0.1,
                "points": 3,
                "settle_s": 0,
                "current_compliance_a": 1e-9,
            },
            "gate2_sweep": {
                "start_v": -0.1,
                "stop_v": 0.1,
                "points": 3,
                "settle_s": 0,
                "current_compliance_a": 1e-9,
            },
            "output": {"directory": tmp_path},
        }
    )


def test_build_sr860_config_commands_maps_recipe_values(tmp_path: Path):
    recipe = dual_gate_lockin_recipe(tmp_path)

    commands = build_sr860_config_commands(recipe.lockin)

    by_field = {command.field: command for command in commands}
    assert by_field["reference_source"].command == "RSRC 0"
    assert by_field["reference_frequency_hz"].command == "FREQ 17.777"
    assert by_field["sine_output_amplitude_v"].command == "SLVL 0.01"
    assert by_field["voltage_input"].command == "ISRC 1"
    assert by_field["voltage_input_range_v"].command == "IRNG 4"
    assert by_field["sensitivity_index"].command == "SCAL 18"
    assert by_field["time_constant_index"].query == "OFLT?"
    assert by_field["filter_slope_db_per_oct"].command == "OFSL 3"
    assert by_field["synchronous_filter"].command == "SYNC 0"


def test_review_sr860_config_commands_includes_parameter_audit(tmp_path: Path):
    recipe = dual_gate_lockin_recipe(tmp_path)

    payload = review_sr860_config_commands(recipe)

    assert payload["ok_for_hardware"] is True
    assert payload["command_count"] == 12
    assert payload["lockin_parameter_audit"]["ok_for_hardware"] is True
    assert payload["commands"][0]["field"] == "reference_source"


def test_review_sr860_config_commands_flags_incomplete_lockin(tmp_path: Path):
    recipe = dual_gate_lockin_recipe(tmp_path, complete_lockin=False)

    payload = review_sr860_config_commands(recipe)

    assert payload["ok_for_hardware"] is False
    assert payload["command_count"] == 0
    missing = payload["lockin_parameter_audit"]["roles"][0]["missing_required_parameters"]
    assert "sensitivity_index" in missing


def test_cli_sr860_command_review_writes_json(tmp_path: Path):
    recipe = tmp_path / "dual_gate_lockin.yaml"
    recipe.write_text(
        """
measurement_name: sr860_cli
gate1_instrument:
  id: keithley_2450
  address: GPIB0::2::INSTR
  voltage_range_v: 0.2
  current_range_a: 1.0e-9
  nplc: 1.0
gate2_instrument:
  id: keithley_2450
  address: GPIB0::3::INSTR
  voltage_range_v: 0.2
  current_range_a: 1.0e-9
  nplc: 1.0
lockin:
  enabled: true
  id: srs_sr860
  address: GPIB0::4::INSTR
  channels: [x, y, r, theta]
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
  directory: data/raw
""".strip(),
        encoding="utf-8",
    )
    output = tmp_path / "sr860_review.json"

    code = cli.main(["sr860-command-review", "dual_gate_lockin_sweep", str(recipe), "--json-output", str(output)])

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert code == 0
    assert payload["ok_for_hardware"] is True
    assert payload["commands"][0]["command"] == "RSRC 0"
    assert payload["commands"][-1]["query"] == "SYNC?"
