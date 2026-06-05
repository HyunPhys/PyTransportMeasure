import json
from pathlib import Path

from pytransport import cli
from pytransport.preflight import DualGateLockInPreflightReport, InstrumentPreflight
from pytransport.instruments.fake import DualGateFakeDeviceState, DualGateFakeLockIn, DualGateFakeSMU


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


def test_cli_dual_gate_lockin_active_sweep_hardware_path_with_guards(tmp_path, monkeypatch):
    recipe = write_dual_gate_lockin_cli_recipe(tmp_path)
    state = DualGateFakeDeviceState(gate1_leak_resistance_ohm=1_000_000_000.0, gate2_leak_resistance_ohm=1_000_000_000.0)
    gate1 = DualGateFakeSMU("gate1", state)
    gate2 = DualGateFakeSMU("gate2", state)
    lockin = DualGateFakeLockIn(state, base_r_v=2e-6, phase_deg=30, noise_std_v=0)

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
    monkeypatch.setattr(cli, "Keithley2450", lambda address, timeout_ms: gate1 if address == "GPIB0::2::INSTR" else gate2)
    monkeypatch.setattr(cli, "SRS_SR860", lambda address, timeout_ms: lockin)

    code = cli.main(
        [
            "dual-gate-lockin",
            str(recipe),
            "--allow-active-sweep",
            "--max-hardware-points",
            "4",
            "--yes",
            "--gate-stats",
            "--plot",
            "--report",
            "--index-path",
            str(tmp_path / "index.jsonl"),
        ]
    )

    assert code == 0
    assert gate1.is_output_on is False
    assert gate2.is_output_on is False
    run_dirs = list((tmp_path / "raw").glob("*dual_gate_lockin_cli"))
    assert len(run_dirs) == 1
    metadata = json.loads((run_dirs[0] / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["measurement_type"] == "dual_gate_lockin_sweep"
    assert metadata["points_written"] == 4
    assert metadata["gate_outputs_enabled"] is False
    assert metadata["outputs_off_after_run"] is True
    assert metadata["hardware_guard"]["default_max_hardware_points"] == 9
    assert metadata["hardware_guard"]["requested_max_hardware_points"] == 4
    assert metadata["hardware_guard"]["raised_above_default"] is False
    assert (run_dirs[0] / "dual_gate_lockin_heatmap.svg").exists()


def test_cli_dual_gate_lockin_blocks_raised_point_guard_without_note(tmp_path):
    recipe = write_dual_gate_lockin_cli_recipe(tmp_path)

    code = cli.main(
        [
            "dual-gate-lockin",
            str(recipe),
            "--allow-active-sweep",
            "--max-hardware-points",
            "12",
            "--yes",
        ]
    )

    assert code == 2
    assert not (tmp_path / "raw").exists()


def test_cli_dual_gate_lockin_records_raised_point_guard_note(tmp_path, monkeypatch):
    recipe = write_dual_gate_lockin_cli_recipe(tmp_path)
    state = DualGateFakeDeviceState(gate1_leak_resistance_ohm=1_000_000_000.0, gate2_leak_resistance_ohm=1_000_000_000.0)
    gate1 = DualGateFakeSMU("gate1", state)
    gate2 = DualGateFakeSMU("gate2", state)
    lockin = DualGateFakeLockIn(state, base_r_v=2e-6, phase_deg=30, noise_std_v=0)

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
    monkeypatch.setattr(cli, "Keithley2450", lambda address, timeout_ms: gate1 if address == "GPIB0::2::INSTR" else gate2)
    monkeypatch.setattr(cli, "SRS_SR860", lambda address, timeout_ms: lockin)

    code = cli.main(
        [
            "dual-gate-lockin",
            str(recipe),
            "--allow-active-sweep",
            "--max-hardware-points",
            "12",
            "--hardware-approval-note",
            "limited lab feedback ok",
            "--yes",
        ]
    )

    assert code == 0
    run_dirs = list((tmp_path / "raw").glob("*dual_gate_lockin_cli"))
    metadata = json.loads((run_dirs[0] / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["hardware_guard"]["requested_max_hardware_points"] == 12
    assert metadata["hardware_guard"]["raised_above_default"] is True
    assert metadata["hardware_guard"]["approval_note"] == "limited lab feedback ok"


def test_cli_dual_gate_lockin_active_sweep_blocks_when_too_many_points(tmp_path, monkeypatch):
    recipe = write_dual_gate_lockin_cli_recipe(tmp_path)

    code = cli.main(
        [
            "dual-gate-lockin",
            str(recipe),
            "--allow-active-sweep",
            "--max-hardware-points",
            "3",
            "--yes",
        ]
    )

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


def test_cli_dual_gate_lockin_smoke_dry_run_writes_readout_csv(tmp_path):
    recipe = write_dual_gate_lockin_cli_recipe(tmp_path)

    code = cli.main(
        [
            "dual-gate-lockin-smoke",
            str(recipe),
            "--dry-run",
            "--samples",
            "3",
            "--interval-s",
            "0",
            "--fake-lockin-r-v",
            "0.000002",
            "--fake-lockin-phase-deg",
            "30",
            "--fake-noise-std",
            "0",
            "--index-path",
            str(tmp_path / "index.jsonl"),
        ]
    )

    assert code == 0
    run_dirs = list((tmp_path / "raw").glob("*dual_gate_lockin_cli_readout_smoke"))
    assert len(run_dirs) == 1
    metadata = json.loads((run_dirs[0] / "metadata.json").read_text(encoding="utf-8"))
    rows = (run_dirs[0] / "lockin_smoke.csv").read_text(encoding="utf-8").strip().splitlines()
    assert metadata["measurement_type"] == "dual_gate_lockin_readout_smoke"
    assert metadata["gate_outputs_enabled"] is False
    assert metadata["points_written"] == 3
    assert len(rows) == 4


def test_cli_dual_gate_lockin_smoke_blocks_when_preflight_fails(tmp_path, monkeypatch):
    recipe = write_dual_gate_lockin_cli_recipe(tmp_path)

    monkeypatch.setattr(
        cli,
        "run_dual_gate_lockin_preflight",
        lambda recipe_path, safety_dir: DualGateLockInPreflightReport(
            recipe_path=str(recipe_path),
            validation_ok=True,
            validation_error=None,
            visa_resources=("GPIB0::2::INSTR",),
            distinct_addresses=True,
            topology_lines=("Layout: hall_bar",),
            gate1=InstrumentPreflight("gate1", "GPIB0::2::INSTR", True, {"idn": "KEITHLEY,2450"}, None),
            gate2=InstrumentPreflight("gate2", "GPIB0::3::INSTR", False, None, None),
            lockin=InstrumentPreflight("lock-in", "GPIB0::4::INSTR", False, None, None),
        ),
    )

    code = cli.main(["dual-gate-lockin-smoke", str(recipe), "--samples", "1", "--interval-s", "0"])

    assert code == 2
    assert not (tmp_path / "raw").exists()


def test_cli_dual_gate_lockin_active_smoke_dry_run_writes_readout_csv(tmp_path):
    recipe = write_dual_gate_lockin_cli_recipe(tmp_path)

    code = cli.main(
        [
            "dual-gate-lockin-active-smoke",
            str(recipe),
            "--dry-run",
            "--gate1-v",
            "0.01",
            "--gate2-v",
            "-0.01",
            "--samples",
            "2",
            "--settle-s",
            "0",
            "--interval-s",
            "0",
            "--fake-lockin-r-v",
            "0.000002",
            "--fake-lockin-phase-deg",
            "30",
            "--fake-noise-std",
            "0",
            "--index-path",
            str(tmp_path / "index.jsonl"),
        ]
    )

    assert code == 0
    run_dirs = list((tmp_path / "raw").glob("*dual_gate_lockin_cli_active_gate_smoke"))
    assert len(run_dirs) == 1
    metadata = json.loads((run_dirs[0] / "metadata.json").read_text(encoding="utf-8"))
    rows = (run_dirs[0] / "active_gate_smoke.csv").read_text(encoding="utf-8").strip().splitlines()
    assert metadata["measurement_type"] == "dual_gate_lockin_active_gate_smoke"
    assert metadata["gate_outputs_enabled"] is False
    assert metadata["outputs_off_after_run"] is True
    assert metadata["points_written"] == 2
    assert len(rows) == 3


def test_cli_dual_gate_lockin_active_smoke_blocks_when_preflight_fails(tmp_path, monkeypatch):
    recipe = write_dual_gate_lockin_cli_recipe(tmp_path)

    monkeypatch.setattr(
        cli,
        "run_dual_gate_lockin_preflight",
        lambda recipe_path, safety_dir: DualGateLockInPreflightReport(
            recipe_path=str(recipe_path),
            validation_ok=True,
            validation_error=None,
            visa_resources=("GPIB0::2::INSTR",),
            distinct_addresses=True,
            topology_lines=("Layout: hall_bar",),
            gate1=InstrumentPreflight("gate1", "GPIB0::2::INSTR", True, {"idn": "KEITHLEY,2450"}, None),
            gate2=InstrumentPreflight("gate2", "GPIB0::3::INSTR", False, None, None),
            lockin=InstrumentPreflight("lock-in", "GPIB0::4::INSTR", False, None, None),
        ),
    )

    code = cli.main(
        [
            "dual-gate-lockin-active-smoke",
            str(recipe),
            "--gate1-v",
            "0.01",
            "--gate2-v",
            "0",
            "--samples",
            "1",
            "--settle-s",
            "0",
            "--interval-s",
            "0",
        ]
    )

    assert code == 2
    assert not (tmp_path / "raw").exists()
