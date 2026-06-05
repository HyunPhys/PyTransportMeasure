import json
from pathlib import Path

from pytransport import cli
from pytransport.recipes import DualGateLockInRecipe
from pytransport.sr860_config import (
    build_sr860_config_commands,
    check_sr860_configure_evidence,
    review_sr860_config_commands,
    run_sr860_configure,
)


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


class FakeConfigurableSR860:
    def __init__(self):
        self.connected = False
        self.closed = False
        self.writes = []
        self.values = {
            "RSRC?": "0",
            "FREQ?": "17.777",
            "SLVL?": "0.01",
            "IVMD?": "0",
            "ISRC?": "1",
            "ICPL?": "0",
            "IGND?": "0",
            "IRNG?": "4",
            "SCAL?": "18",
            "OFLT?": "10",
            "OFSL?": "3",
            "SYNC?": "0",
        }

    def connect(self):
        self.connected = True

    def probe(self):
        return {"idn": "Stanford_Research_Systems,SR860,000111,v1.23", "setting_sensitivity_index": self.values["SCAL?"]}

    def write(self, command):
        self.writes.append(command)

    def query(self, command):
        return self.values[command]

    def close(self):
        self.closed = True


def test_run_sr860_configure_records_transcript_and_closes(tmp_path: Path):
    recipe = dual_gate_lockin_recipe(tmp_path)
    lockin = FakeConfigurableSR860()

    payload = run_sr860_configure(
        recipe,
        lockin,
        recipe_path="recipe.yaml",
        hardware_approval_note="lab reviewed SR860 output wiring",
    )

    assert payload["completed"] is True
    assert payload["apply"]["matched"] is True
    assert payload["apply"]["steps"][0]["command"] == "RSRC 0"
    assert payload["probe_before"]["idn"].startswith("Stanford_Research_Systems")
    assert lockin.closed is True


def test_sr860_configure_evidence_check_passes_for_current_recipe(tmp_path: Path):
    recipe = dual_gate_lockin_recipe(tmp_path)
    lockin = FakeConfigurableSR860()
    configure_payload = run_sr860_configure(
        recipe,
        lockin,
        recipe_path="recipe.yaml",
        hardware_approval_note="lab reviewed SR860 output wiring",
    )

    payload = check_sr860_configure_evidence(recipe, configure_payload)

    assert payload["ok"] is True
    assert payload["expected_command_count"] == 12
    assert payload["transcript_command_count"] == 12
    assert all(check["passed"] for check in payload["checks"])


def test_sr860_configure_evidence_check_fails_when_recipe_changes(tmp_path: Path):
    recipe = dual_gate_lockin_recipe(tmp_path)
    configure_payload = run_sr860_configure(
        recipe,
        FakeConfigurableSR860(),
        recipe_path="recipe.yaml",
        hardware_approval_note="lab reviewed SR860 output wiring",
    )
    changed = recipe.model_copy(
        update={
            "lockin": recipe.lockin.model_copy(update={"sensitivity_index": 19}),
        }
    )

    payload = check_sr860_configure_evidence(changed, configure_payload)
    checks = {check["name"]: check for check in payload["checks"]}

    assert payload["ok"] is False
    assert checks["review_commands_match_recipe"]["passed"] is False
    assert checks["apply_steps_match_recipe"]["passed"] is False


def test_sr860_configure_evidence_check_fails_when_step_readback_was_bad(tmp_path: Path):
    recipe = dual_gate_lockin_recipe(tmp_path)
    configure_payload = run_sr860_configure(
        recipe,
        FakeConfigurableSR860(),
        recipe_path="recipe.yaml",
        hardware_approval_note="lab reviewed SR860 output wiring",
    )
    configure_payload["apply"]["steps"][1]["actual_readback"] = "18.001"

    payload = check_sr860_configure_evidence(recipe, configure_payload)
    checks = {check["name"]: check for check in payload["checks"]}

    assert payload["ok"] is False
    assert checks["apply_steps_match_recipe"]["passed"] is False


def test_cli_sr860_configure_requires_allow_write(tmp_path: Path):
    recipe = tmp_path / "dual_gate_lockin.yaml"
    recipe.write_text(
        """
measurement_name: sr860_cli_blocked
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

    code = cli.main(["sr860-configure", "dual_gate_lockin_sweep", str(recipe), "--yes"])

    assert code == 2


def test_cli_sr860_configure_writes_json_with_fake_lockin(tmp_path: Path, monkeypatch):
    recipe = tmp_path / "dual_gate_lockin.yaml"
    recipe.write_text(
        """
measurement_name: sr860_cli_apply
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
    output = tmp_path / "configure.json"
    fake = FakeConfigurableSR860()
    monkeypatch.setattr(cli, "SRS_SR860", lambda address, timeout_ms: fake)

    code = cli.main(
        [
            "sr860-configure",
            "dual_gate_lockin_sweep",
            str(recipe),
            "--allow-write",
            "--hardware-approval-note",
            "lab reviewed SR860 output wiring",
            "--json-output",
            str(output),
            "--yes",
        ]
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert code == 0
    assert payload["completed"] is True
    assert payload["apply"]["steps"][0]["command"] == "RSRC 0"
    assert fake.writes[-1] == "SYNC 0"


def test_cli_sr860_configure_check_writes_json(tmp_path: Path):
    recipe_model = dual_gate_lockin_recipe(tmp_path)
    recipe = tmp_path / "dual_gate_lockin.yaml"
    recipe.write_text(recipe_model.model_dump_json(indent=2), encoding="utf-8")
    configure = tmp_path / "configure.json"
    configure.write_text(
        json.dumps(
            run_sr860_configure(
                recipe_model,
                FakeConfigurableSR860(),
                recipe_path=recipe,
                hardware_approval_note="lab reviewed SR860 output wiring",
            )
        ),
        encoding="utf-8",
    )
    output = tmp_path / "configure_check.json"

    code = cli.main(
        [
            "sr860-configure-check",
            "dual_gate_lockin_sweep",
            str(recipe),
            str(configure),
            "--json-output",
            str(output),
        ]
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert code == 0
    assert payload["ok"] is True
    assert payload["checks"][0]["name"] == "schema"
