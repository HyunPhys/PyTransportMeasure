import json

from pytransport.cli import main
from pytransport.four_terminal_dc import (
    format_four_terminal_dc_design_gate,
    inspect_four_terminal_dc_design_gate,
)


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
    assert ("blocker", "schema") in issues
    assert not any(issue.field.startswith("instrument.") for issue in report.issues)


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
