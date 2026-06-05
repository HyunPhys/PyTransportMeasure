import json

from pytransport.cli import main
from pytransport.measurement_modes import (
    format_measurement_mode_matrix,
    measurement_mode_by_key,
    measurement_mode_matrix_payload,
)


def test_measurement_mode_matrix_covers_target_hall_bar_path():
    payload = measurement_mode_matrix_payload()
    modes = {mode["key"]: mode for mode in payload["modes"]}

    assert payload["schema"] == "pytransport.measurement_modes.v1"
    assert set(modes) == {
        "two_terminal_dc",
        "four_terminal_dc",
        "two_terminal_ac",
        "four_terminal_ac",
        "hall_dual_gate_lockin",
    }
    assert modes["two_terminal_dc"]["status"] == "hardware_verified"
    assert modes["four_terminal_dc"]["status"] == "hardware_smoke_ready"
    assert modes["hall_dual_gate_lockin"]["measurement_type"] == "dual_gate_lockin_sweep"
    assert "gate1/gate2 NPLC" in modes["hall_dual_gate_lockin"]["guarded_parameters"]


def test_measurement_mode_matrix_text_and_lookup():
    mode = measurement_mode_by_key("four_terminal_ac")
    text = format_measurement_mode_matrix(verbose=True)

    assert mode.geometry == "four_terminal, 4-terminal"
    assert "PyTransportMeasure Measurement Mode Execution Matrix" in text
    assert "Two-terminal DC I-V" in text
    assert "Hall-bar dual-gate lock-in suite" in text
    assert "SR860 differential voltage input" in text


def test_cli_measurement_modes_outputs_text_and_json(tmp_path, capsys):
    assert main(["measurement-modes"]) == 0
    text = capsys.readouterr().out
    assert "two_terminal_dc" in text
    assert "hall_dual_gate_lockin" in text

    output = tmp_path / "measurement_modes.json"
    assert main(["measurement-modes", "--json-output", str(output)]) == 0
    saved = json.loads(output.read_text(encoding="utf-8"))
    assert saved["mode_count"] == 5
    capsys.readouterr()

    assert main(["measurement-modes", "--json"]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["schema"] == "pytransport.measurement_modes.v1"
