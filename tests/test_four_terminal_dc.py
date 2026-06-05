import csv
import json
from pathlib import Path

import pytest

from pytransport.cli import main
from pytransport.four_terminal_dc import (
    format_four_terminal_dc_command_review,
    format_four_terminal_dc_preflight,
    format_four_terminal_dc_design_gate,
    inspect_four_terminal_dc_design_gate,
    review_four_terminal_dc_active_run_commands,
    run_four_terminal_dc_active,
    run_four_terminal_dc_dry_run,
    run_four_terminal_dc_preflight,
)
from pytransport.instruments.fake import FakeSMU
from pytransport.recipes import FourTerminalDCRecipe, load_four_terminal_dc_recipe, load_named_safety_preset


def write_candidate_recipe(path):
    path.write_text(
        """
measurement_name: future_four_terminal_dc
measurement_geometry:
  terminal_count: 4
  method: four_terminal
  notes: Future Keithley remote-sense DC recipe; design gate only.
instrument:
  id: keithley_2450
  address: GPIB0::2::INSTR
  terminal: FRONT
  voltage_range_v: 0.1
  current_range_a: 1.0e-7
  nplc: 1.0
sweep:
  mode: linear_one_way
  start_v: -0.01
  stop_v: 0.01
  points: 3
  delay_s: 0.1
  current_compliance_a: 1.0e-7
""".lstrip(),
        encoding="utf-8",
    )


def write_schema_draft_recipe(
    path,
    *,
    terminal_plane="FRONT",
    instrument_terminal="FRONT",
    sense_lo_contact="V-",
    output_dir=None,
):
    output_block = "" if output_dir is None else f"output:\n  directory: {output_dir}\n"
    path.write_text(
        f"""
measurement_name: schema_draft_four_terminal_dc
measurement_geometry:
  terminal_count: 4
  method: four_terminal
dc_sense_mode: remote_4wire
instrument:
  id: keithley_2450
  address: GPIB0::2::INSTR
  terminal: {instrument_terminal}
  voltage_range_v: 0.1
  current_range_a: 1.0e-7
  nplc: 1.0
contacts:
  source_contact: S
  drain_contact: D
  sense_hi_contact: V+
  sense_lo_contact: {sense_lo_contact}
  terminal_plane: {terminal_plane}
sweep:
  mode: linear_one_way
  start_v: -0.01
  stop_v: 0.01
  points: 3
  delay_s: 0.1
  current_compliance_a: 1.0e-7
{output_block.rstrip()}
implementation_status: schema_draft_non_executable
""".lstrip(),
        encoding="utf-8",
    )


class FakeKeithleyFourTerminalPreflight:
    def __init__(self, address, timeout_ms):
        self.address = address
        self.timeout_ms = timeout_ms
        self.connected = False
        self.closed = False

    def connect(self):
        self.connected = True

    def probe(self):
        return {
            "address": self.address,
            "idn": "KEITHLEY INSTRUMENTS,MODEL 2450,1234567,1.0",
            "language": "SCPI",
            "system_error": '0,"No error"',
        }

    def read_current_remote_sense(self):
        return "0"

    def read_voltage_source_config(self):
        return {
            "source_function": "VOLT",
            "sense_function": '"CURR"',
            "terminal": "FRONT",
            "current_nplc": "1",
            "current_range": "1.0E-7",
            "current_range_auto": "0",
            "voltage_range": "0.1",
            "source_delay": "0.1",
            "voltage_readback": "1",
            "source_current_limit": None,
            "source_current_limit_query": None,
        }

    def close(self):
        self.closed = True


class FourTerminalActiveFakeSMU(FakeSMU):
    def __init__(self, address="FAKE::2450", timeout_ms=10000):
        super().__init__(resistance_ohm=1_000_000, noise_std_a=0)
        self.address = address
        self.timeout_ms = timeout_ms
        self.remote_sense_enabled = False
        self.remote_sense_history = []

    def probe(self):
        payload = super().probe()
        payload.update({"address": self.address, "language": "SCPI"})
        return payload

    def configure_current_remote_sense(self, enabled):
        self.remote_sense_enabled = bool(enabled)
        self.remote_sense_history.append(bool(enabled))

    def read_current_remote_sense(self):
        return "1" if self.remote_sense_enabled else "0"


def test_four_terminal_dc_schema_draft_sample_loads():
    recipe = load_four_terminal_dc_recipe("configs/recipes/four_terminal_dc_schema_draft.yaml")

    assert recipe.measurement_name == "four_terminal_dc_schema_draft"
    assert recipe.measurement_geometry.method == "four_terminal"
    assert recipe.measurement_geometry.terminal_count == 4
    assert recipe.dc_sense_mode == "remote_4wire"
    assert recipe.contacts.source_contact == "S"
    assert recipe.contacts.sense_hi_contact == "V+"
    assert recipe.instrument.nplc == 1.0
    assert recipe.implementation_status == "schema_draft_non_executable"


def test_four_terminal_dc_schema_requires_distinct_contacts_and_terminal_match(tmp_path):
    duplicate = tmp_path / "duplicate.yaml"
    write_schema_draft_recipe(duplicate, sense_lo_contact="S")
    with pytest.raises(Exception, match="force and sense contacts must be distinct"):
        FourTerminalDCRecipe.model_validate_json(load_four_terminal_dc_recipe(duplicate).model_dump_json())

    mismatch = tmp_path / "mismatch.yaml"
    write_schema_draft_recipe(mismatch, terminal_plane="REAR", instrument_terminal="FRONT")
    with pytest.raises(Exception, match="instrument.terminal must match contacts.terminal_plane"):
        load_four_terminal_dc_recipe(mismatch)


def test_four_terminal_dc_design_gate_blocks_active_hardware_and_lists_scpi():
    report = inspect_four_terminal_dc_design_gate()
    text = format_four_terminal_dc_design_gate(report)

    assert report.ready_for_implementation is False
    assert report.active_hardware_run_allowed is False
    assert any(":SENS:CURR:RSEN ON" in command for command in report.required_driver_commands)
    assert any(":SENS:CURR:RSEN?" in query for query in report.required_readback_queries)
    assert "No active four-terminal DC runner" in text


def test_four_terminal_dc_design_gate_accepts_candidate_recipe_but_keeps_blockers(tmp_path):
    recipe = tmp_path / "four_terminal_dc.yaml"
    write_candidate_recipe(recipe)

    report = inspect_four_terminal_dc_design_gate(recipe)
    issues = {(issue.severity, issue.field) for issue in report.issues}

    assert report.recipe_path == str(recipe)
    assert report.measurement_name == "future_four_terminal_dc"
    assert report.measurement_geometry == {"method": "four_terminal", "terminal_count": 4, "notes": "Future Keithley remote-sense DC recipe; design gate only."}
    assert ("blocker", "runner") in issues
    assert ("info", "driver") in issues
    assert ("info", "preflight") in issues
    assert ("warning", "schema") in issues
    assert not any(issue.field.startswith("instrument.") for issue in report.issues)


def test_four_terminal_dc_design_gate_accepts_schema_draft_recipe(tmp_path):
    recipe = tmp_path / "schema_draft.yaml"
    write_schema_draft_recipe(recipe)

    report = inspect_four_terminal_dc_design_gate(recipe)
    issues = {(issue.severity, issue.field) for issue in report.issues}

    assert report.measurement_name == "schema_draft_four_terminal_dc"
    assert ("warning", "schema") not in issues
    assert ("info", "driver") in issues
    assert ("info", "preflight") in issues


def test_four_terminal_dc_preflight_dry_check_keeps_active_hardware_blocked():
    report = run_four_terminal_dc_preflight(
        "configs/recipes/four_terminal_dc_schema_draft.yaml",
        dry_check=True,
    )
    text = format_four_terminal_dc_preflight(report)

    assert report.preflight_passed is True
    assert report.dry_check is True
    assert report.hardware_checked is False
    assert report.active_hardware_run_allowed is False
    assert any(check.name == "explicit_nplc" and check.ok for check in report.checks)
    assert "NPLC is a measurement condition" in text


def test_four_terminal_dc_preflight_probes_remote_sense_without_runner():
    report = run_four_terminal_dc_preflight(
        "configs/recipes/four_terminal_dc_schema_draft.yaml",
        instrument_factory=FakeKeithleyFourTerminalPreflight,
    )
    checks = {check.name: check for check in report.checks}

    assert report.preflight_passed is True
    assert report.hardware_checked is True
    assert report.hardware_connected is True
    assert report.active_hardware_run_allowed is False
    assert report.language == "SCPI"
    assert report.remote_sense_readback == "0"
    assert checks["remote_sense_readback_available"].ok is True
    assert checks["nplc_readback_available"].ok is True
    assert checks["current_range_readback_available"].ok is True
    assert checks["voltage_range_readback_available"].ok is True


def test_four_terminal_dc_preflight_reports_failed_hardware_readback():
    class FailingRemoteSense(FakeKeithleyFourTerminalPreflight):
        def read_current_remote_sense(self):
            return 'ERROR after :SENS:CURR:RSEN?: -113,"Undefined header"'

    report = run_four_terminal_dc_preflight(
        "configs/recipes/four_terminal_dc_schema_draft.yaml",
        instrument_factory=FailingRemoteSense,
    )

    assert report.preflight_passed is False
    assert any(check.name == "remote_sense_readback_available" and not check.ok for check in report.checks)


def test_four_terminal_dc_dry_run_writes_metadata_without_active_output(tmp_path):
    recipe_path = tmp_path / "four_terminal_dc.yaml"
    write_schema_draft_recipe(recipe_path, output_dir=tmp_path.as_posix())
    recipe = load_four_terminal_dc_recipe(recipe_path)
    safety = load_named_safety_preset(recipe.safety_preset)

    metadata = run_four_terminal_dc_dry_run(
        recipe,
        safety,
        recipe_path=recipe_path,
        fake_resistance_ohm=1_000_000,
        fake_noise_std_a=0,
    )
    run_dir = Path(metadata["run_dir"])
    rows = list(csv.DictReader((run_dir / "points.csv").open(newline="", encoding="utf-8")))
    saved_metadata = json.loads((run_dir / "metadata.json").read_text(encoding="utf-8"))

    assert metadata["completed"] is True
    assert metadata["dry_run"] is True
    assert metadata["active_hardware_run_allowed"] is False
    assert metadata["remote_sense"]["configured_in_dry_run"] is False
    assert metadata["configured_smu"]["nplc"] == pytest.approx(1.0)
    assert metadata["configured_smu_readback"]["current_nplc"] == "1"
    assert len(rows) == 3
    assert rows[0]["voltage_v"] == "-0.01"
    assert saved_metadata["measurement_type"] == "four_terminal_dc"
    assert saved_metadata["contact_map"]["sense_hi_contact"] == "V+"


def test_four_terminal_dc_dry_run_saves_partial_metadata_on_limit(tmp_path):
    recipe_path = tmp_path / "four_terminal_dc.yaml"
    write_schema_draft_recipe(recipe_path, output_dir=tmp_path.as_posix())
    recipe = load_four_terminal_dc_recipe(recipe_path)
    safety = load_named_safety_preset(recipe.safety_preset)

    metadata = run_four_terminal_dc_dry_run(
        recipe,
        safety,
        recipe_path=recipe_path,
        fake_resistance_ohm=1,
        fake_noise_std_a=0,
    )
    run_dir = Path(metadata["run_dir"])
    saved_metadata = json.loads((run_dir / "metadata.json").read_text(encoding="utf-8"))

    assert metadata["completed"] is False
    assert metadata["error_type"] == "SafetyLimitError"
    assert metadata["points_written"] == 0
    assert saved_metadata["triggered_limit"] == "instrument_compliance"


def test_four_terminal_dc_command_review_lists_guarded_sequence_without_output():
    report = review_four_terminal_dc_active_run_commands("configs/recipes/four_terminal_dc_schema_draft.yaml")
    text = format_four_terminal_dc_command_review(report)
    commands = [step.command for step in report.command_steps]

    assert report.active_hardware_run_allowed is False
    assert report.active_runner_ready is False
    assert report.evidence_passed is False
    assert ":SENS:CURR:RSEN ON" in commands
    assert ":SENS:CURR:RSEN OFF" in commands
    assert ":OUTP ON" in commands
    assert commands.index(":SENS:CURR:RSEN ON") < commands.index(":OUTP ON")
    assert commands.index(":SOUR:VOLT 0") < commands.index(":OUTP ON")
    assert any(step.command == ":SENS:CURR:NPLC 1.0" for step in report.command_steps)
    assert "Active hardware run allowed: False" in text


def test_four_terminal_dc_command_review_accepts_preflight_and_dry_run_evidence(tmp_path):
    recipe_path = tmp_path / "four_terminal_dc.yaml"
    write_schema_draft_recipe(recipe_path, output_dir=tmp_path.as_posix())
    preflight = run_four_terminal_dc_preflight(
        recipe_path,
        instrument_factory=FakeKeithleyFourTerminalPreflight,
    )
    preflight_path = tmp_path / "preflight.json"
    preflight_path.write_text(json.dumps(preflight.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
    recipe = load_four_terminal_dc_recipe(recipe_path)
    safety = load_named_safety_preset(recipe.safety_preset)
    metadata = run_four_terminal_dc_dry_run(recipe, safety, recipe_path=recipe_path, fake_noise_std_a=0)
    metadata_path = Path(metadata["metadata_path"])

    report = review_four_terminal_dc_active_run_commands(
        recipe_path,
        preflight_json=preflight_path,
        dry_run_metadata=metadata_path,
    )

    assert report.evidence_passed is True
    assert report.active_hardware_run_allowed is False
    assert all(check.ok for check in report.evidence_checks)


def write_passing_command_review_json(tmp_path, recipe_path):
    preflight = run_four_terminal_dc_preflight(
        recipe_path,
        instrument_factory=FakeKeithleyFourTerminalPreflight,
    )
    preflight_path = tmp_path / "preflight.json"
    preflight_path.write_text(json.dumps(preflight.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
    recipe = load_four_terminal_dc_recipe(recipe_path)
    safety = load_named_safety_preset(recipe.safety_preset)
    metadata = run_four_terminal_dc_dry_run(recipe, safety, recipe_path=recipe_path, fake_noise_std_a=0)
    review = review_four_terminal_dc_active_run_commands(
        recipe_path,
        preflight_json=preflight_path,
        dry_run_metadata=metadata["metadata_path"],
    )
    review_path = tmp_path / "command_review.json"
    review_path.write_text(json.dumps(review.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
    return review_path


def test_four_terminal_dc_active_runner_uses_remote_sense_and_cleanup(tmp_path):
    recipe_path = tmp_path / "four_terminal_dc.yaml"
    write_schema_draft_recipe(recipe_path, output_dir=tmp_path.as_posix())
    review_path = write_passing_command_review_json(tmp_path, recipe_path)
    recipe = load_four_terminal_dc_recipe(recipe_path)
    safety = load_named_safety_preset(recipe.safety_preset)
    smu = FourTerminalActiveFakeSMU()

    metadata = run_four_terminal_dc_active(
        recipe,
        safety,
        smu,
        recipe_path=recipe_path,
        command_review_json=review_path,
        hardware_approval_note="lab fixture reviewed; fake active test",
    )
    saved = json.loads(Path(metadata["metadata_path"]).read_text(encoding="utf-8"))

    assert metadata["completed"] is True
    assert metadata["dry_run"] is False
    assert metadata["remote_sense"]["enabled_readback_ok"] is True
    assert metadata["remote_sense"]["disabled_after_run_readback"] == "0"
    assert smu.remote_sense_history == [True, False]
    assert metadata["output_state"]["instrument"]["off_after_run"] is True
    assert saved["hardware_guard"]["command_review_evidence_passed"] is True


def test_four_terminal_dc_active_runner_rejects_nonpassing_command_review(tmp_path):
    recipe_path = tmp_path / "four_terminal_dc.yaml"
    write_schema_draft_recipe(recipe_path, output_dir=tmp_path.as_posix())
    bad_review = review_four_terminal_dc_active_run_commands(recipe_path)
    bad_review_path = tmp_path / "bad_command_review.json"
    bad_review_path.write_text(json.dumps(bad_review.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
    recipe = load_four_terminal_dc_recipe(recipe_path)
    safety = load_named_safety_preset(recipe.safety_preset)

    with pytest.raises(ValueError, match="evidence_passed=true"):
        run_four_terminal_dc_active(
            recipe,
            safety,
            FourTerminalActiveFakeSMU(),
            recipe_path=recipe_path,
            command_review_json=bad_review_path,
            hardware_approval_note="should fail before connecting",
        )


def test_cli_four_terminal_dc_design_gate_outputs_text_and_json(tmp_path, capsys):
    recipe = tmp_path / "four_terminal_dc.yaml"
    output = tmp_path / "design_gate.json"
    write_candidate_recipe(recipe)

    assert main(["four-terminal-dc-design-gate", str(recipe)]) == 0
    text = capsys.readouterr().out
    assert "Four-terminal DC design gate" in text
    assert "Active hardware run allowed: False" in text

    assert main(["four-terminal-dc-design-gate", str(recipe), "--json-output", str(output)]) == 0
    saved = json.loads(output.read_text(encoding="utf-8"))
    assert saved["active_hardware_run_allowed"] is False
    capsys.readouterr()

    assert main(["four-terminal-dc-design-gate", "--json"]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["ready_for_implementation"] is False


def test_cli_four_terminal_dc_validate_outputs_pass_and_json(capsys):
    recipe = "configs/recipes/four_terminal_dc_schema_draft.yaml"

    assert main(["four-terminal-dc-validate", recipe]) == 0
    text = capsys.readouterr().out
    assert "Four-terminal DC recipe validation: PASS" in text
    assert "Active hardware run allowed: False" in text

    assert main(["four-terminal-dc-validate", recipe, "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["implementation_status"] == "schema_draft_non_executable"


def test_cli_four_terminal_dc_preflight_dry_check_outputs_text_and_json(tmp_path, capsys):
    recipe = "configs/recipes/four_terminal_dc_schema_draft.yaml"
    output = tmp_path / "preflight.json"

    assert main(["four-terminal-dc-preflight", recipe, "--dry-check"]) == 0
    text = capsys.readouterr().out
    assert "Four-terminal DC preflight" in text
    assert "Active hardware run allowed: False" in text
    assert "Hardware checked: False" in text

    assert main(["four-terminal-dc-preflight", recipe, "--dry-check", "--json-output", str(output)]) == 0
    saved = json.loads(output.read_text(encoding="utf-8"))
    assert saved["dry_check"] is True
    assert saved["preflight_passed"] is True
    capsys.readouterr()

    assert main(["four-terminal-dc-preflight", recipe, "--dry-check", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["active_hardware_run_allowed"] is False


def test_cli_four_terminal_dc_requires_dry_run(capsys):
    recipe = "configs/recipes/four_terminal_dc_schema_draft.yaml"

    assert main(["four-terminal-dc", recipe]) == 2
    assert "hardware output is guarded" in capsys.readouterr().err


def test_cli_four_terminal_dc_dry_run_writes_artifacts(tmp_path, capsys):
    recipe = tmp_path / "four_terminal_dc.yaml"
    write_schema_draft_recipe(recipe, output_dir=tmp_path.as_posix())

    assert main(["four-terminal-dc", str(recipe), "--dry-run", "--fake-resistance-ohm", "1000000"]) == 0
    text = capsys.readouterr().out
    run_dir_line = next(line for line in text.splitlines() if line.startswith("Run directory: "))
    run_dir = Path(run_dir_line.split(": ", maxsplit=1)[1])
    metadata = json.loads((run_dir / "metadata.json").read_text(encoding="utf-8"))

    assert "Four-terminal DC dry-run" in text
    assert "Active hardware run allowed: False" in text
    assert metadata["completed"] is True
    assert metadata["configured_smu"]["nplc"] == pytest.approx(1.0)


def test_cli_four_terminal_dc_command_review_outputs_text_and_json(tmp_path, capsys):
    recipe = "configs/recipes/four_terminal_dc_schema_draft.yaml"
    output = tmp_path / "command_review.json"

    assert main(["four-terminal-dc-command-review", recipe]) == 0
    text = capsys.readouterr().out
    assert "Four-terminal DC active-run command review" in text
    assert "Active hardware run allowed: False" in text
    assert ":SENS:CURR:RSEN ON" in text

    assert main(["four-terminal-dc-command-review", recipe, "--json-output", str(output)]) == 0
    saved = json.loads(output.read_text(encoding="utf-8"))
    assert saved["active_hardware_run_allowed"] is False
    capsys.readouterr()

    assert main(["four-terminal-dc-command-review", recipe, "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["active_runner_ready"] is False


def test_cli_four_terminal_dc_active_run_requires_command_review(capsys):
    recipe = "configs/recipes/four_terminal_dc_schema_draft.yaml"

    assert main(["four-terminal-dc", recipe, "--allow-active-run", "--hardware-approval-note", "fixture checked"]) == 2
    assert "--command-review-json is required" in capsys.readouterr().err


def test_cli_four_terminal_dc_active_run_with_fakes_writes_metadata(tmp_path, monkeypatch, capsys):
    import pytransport.cli as cli_module

    recipe_path = tmp_path / "four_terminal_dc.yaml"
    write_schema_draft_recipe(recipe_path, output_dir=tmp_path.as_posix())
    review_path = write_passing_command_review_json(tmp_path, recipe_path)
    preflight = run_four_terminal_dc_preflight(
        recipe_path,
        instrument_factory=FakeKeithleyFourTerminalPreflight,
    )
    monkeypatch.setattr(cli_module, "run_four_terminal_dc_preflight", lambda recipe: preflight)
    monkeypatch.setattr(cli_module, "Keithley2450", FourTerminalActiveFakeSMU)

    assert main(
        [
            "four-terminal-dc",
            str(recipe_path),
            "--allow-active-run",
            "--command-review-json",
            str(review_path),
            "--hardware-approval-note",
            "fixture checked in fake test",
            "--max-hardware-points",
            "3",
            "--yes",
        ]
    ) == 0
    text = capsys.readouterr().out
    metadata_line = next(line for line in text.splitlines() if line.startswith("Metadata: "))
    metadata = json.loads(Path(metadata_line.split(": ", maxsplit=1)[1]).read_text(encoding="utf-8"))

    assert "command-review evidence accepted" in text
    assert metadata["completed"] is True
    assert metadata["remote_sense"]["enabled_readback_ok"] is True
