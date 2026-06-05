import json
from pathlib import Path

from pytransport import cli
from pytransport.preflight import DualGateLockInPreflightReport, InstrumentPreflight


def write_dual_gate_lockin_cli_recipe(tmp_path: Path) -> Path:
    recipe = tmp_path / "dual_gate_lockin_cli.yaml"
    output_dir = str(tmp_path / "raw").replace("\\", "/")
    recipe.write_text(
        f"""
measurement_name: dual_gate_lockin_cli
safety_preset: nano_device_safe
measurement_geometry:
  terminal_count: 2
  method: two_terminal
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
  address: GPIB0::4::INSTR
  channels: [x, y, r, theta]
  read_timing: after_dc_settle
topology:
  device_layout: hall_bar
  gate1_role: top_gate
  gate2_role: back_gate
  source_contact: S
  drain_contact: D
  lockin_input_mode: voltage
  lockin_input_contacts: [Vxx+, Vxx-]
  excitation_source: sr860_sine_out
  excitation_contacts: [S, D]
  excitation_amplitude_v: 0.01
  current_bias_resistor_ohm: 1000000
gate1_sweep:
  start_v: -0.1
  stop_v: 0.1
  points: 2
  settle_s: 0.0
  current_compliance_a: 1.0e-8
gate2_sweep:
  start_v: -0.1
  stop_v: 0.1
  points: 2
  settle_s: 0.0
  current_compliance_a: 1.0e-8
output:
  directory: {output_dir}
checks:
  require_completed: true
  min_points: 4
""".strip(),
        encoding="utf-8",
    )
    return recipe


def test_cli_dual_gate_lockin_dry_run_writes_artifacts(tmp_path):
    recipe = write_dual_gate_lockin_cli_recipe(tmp_path)

    code = cli.main(
        [
            "dual-gate-lockin",
            str(recipe),
            "--dry-run",
            "--summary",
            "--plot",
            "--report",
            "--gate-stats",
            "--fake-noise-std",
            "0",
            "--index-path",
            str(tmp_path / "index.jsonl"),
        ]
    )

    assert code == 0
    run_dirs = list((tmp_path / "raw").glob("*dual_gate_lockin_cli"))
    assert len(run_dirs) == 1
    metadata = json.loads((run_dirs[0] / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["measurement_type"] == "dual_gate_lockin_sweep"
    assert metadata["points_written"] == 4
    assert (run_dirs[0] / "dual_gate_lockin_heatmap.svg").exists()
    assert (run_dirs[0] / "dual_gate_lockin_report.md").exists()
    assert (run_dirs[0] / "dual_gate_lockin_stats.csv").exists()


def test_cli_dual_gate_lockin_hardware_run_is_blocked(tmp_path, monkeypatch):
    recipe = write_dual_gate_lockin_cli_recipe(tmp_path)

    monkeypatch.setattr(
        cli,
        "run_dual_gate_lockin_preflight",
        lambda recipe_path, safety_dir: DualGateLockInPreflightReport(
            recipe_path=str(recipe_path),
            validation_ok=True,
            validation_error=None,
            visa_resources=("GPIB0::2::INSTR", "GPIB0::3::INSTR", "GPIB0::4::INSTR"),
            distinct_addresses=True,
            topology_lines=("Layout: hall_bar",),
            gate1=InstrumentPreflight("gate1", "GPIB0::2::INSTR", True, {"idn": "KEITHLEY,2450"}, None),
            gate2=InstrumentPreflight("gate2", "GPIB0::3::INSTR", True, {"idn": "KEITHLEY,2450"}, None),
            lockin=InstrumentPreflight("lock-in", "GPIB0::4::INSTR", True, {"idn": "SRS,SR860"}, None),
        ),
    )

    code = cli.main(["dual-gate-lockin", str(recipe)])

    assert code == 2
    assert not (tmp_path / "raw").exists()


def test_cli_dual_gate_lockin_preflight_command(tmp_path, monkeypatch):
    recipe = write_dual_gate_lockin_cli_recipe(tmp_path)

    def fake_preflight(recipe_path, safety_dir):
        return DualGateLockInPreflightReport(
            recipe_path=str(recipe_path),
            validation_ok=True,
            validation_error=None,
            visa_resources=("GPIB0::2::INSTR", "GPIB0::3::INSTR", "GPIB0::4::INSTR"),
            distinct_addresses=True,
            topology_lines=("Layout: hall_bar",),
            gate1=InstrumentPreflight("gate1", "GPIB0::2::INSTR", True, {"idn": "KEITHLEY,2450"}, None),
            gate2=InstrumentPreflight("gate2", "GPIB0::3::INSTR", True, {"idn": "KEITHLEY,2450"}, None),
            lockin=InstrumentPreflight("lock-in", "GPIB0::4::INSTR", True, {"idn": "SRS,SR860"}, None),
        )

    monkeypatch.setattr(cli, "run_dual_gate_lockin_preflight", fake_preflight)

    code = cli.main(["dual-gate-lockin-preflight", str(recipe)])

    assert code == 0
