import json

import pytest

from pytransport.cli import main
from pytransport.four_terminal_dc import (
    format_four_terminal_dc_design_gate,
    inspect_four_terminal_dc_design_gate,
)
from pytransport.recipes import FourTerminalDCRecipe, load_four_terminal_dc_recipe


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


def write_schema_draft_recipe(path, *, terminal_plane="FRONT", instrument_terminal="FRONT", sense_lo_contact="V-"):
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
implementation_status: schema_draft_non_executable
""".lstrip(),
        encoding="utf-8",
    )


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
    assert ("blocker", "preflight") in issues
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
    assert ("blocker", "preflight") in issues


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
