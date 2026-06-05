import json
from pathlib import Path

from pytransport import cli


def write_dual_gate_cli_recipe(tmp_path: Path) -> Path:
    recipe = tmp_path / "dual_gate_cli.yaml"
    output_dir = str(tmp_path / "raw").replace("\\", "/")
    recipe.write_text(
        f"""
measurement_name: dual_gate_cli
safety_preset: nano_device_safe
measurement_geometry:
  terminal_count: 2
  method: two_terminal
drain_instrument:
  id: keithley_2450
  address: GPIB0::2::INSTR
  voltage_range_v: 0.1
  current_range_a: 1.0e-6
  nplc: 1.0
gate1_instrument:
  id: keithley_2450
  address: GPIB0::3::INSTR
  voltage_range_v: 0.2
  current_range_a: 1.0e-9
  nplc: 1.0
gate2_instrument:
  id: keithley_2450
  address: GPIB0::4::INSTR
  voltage_range_v: 0.2
  current_range_a: 1.0e-9
  nplc: 1.0
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
drain_sweep:
  mode: linear_one_way
  start_v: -0.01
  stop_v: 0.01
  points: 3
  delay_s: 0.0
  current_compliance_a: 1.0e-7
output:
  directory: {output_dir}
checks:
  require_completed: true
  min_points: 12
""".strip(),
        encoding="utf-8",
    )
    return recipe


def test_cli_dual_gate_dry_run_writes_artifacts(tmp_path):
    recipe = write_dual_gate_cli_recipe(tmp_path)

    code = cli.main(
        [
            "dual-gate",
            str(recipe),
            "--dry-run",
            "--summary",
            "--plot",
            "--report",
            "--gate-stats",
            "--fake-noise-std-a",
            "0",
            "--index-path",
            str(tmp_path / "index.jsonl"),
        ]
    )

    assert code == 0
    run_dirs = list((tmp_path / "raw").glob("*dual_gate_cli"))
    assert len(run_dirs) == 1
    metadata = json.loads((run_dirs[0] / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["measurement_type"] == "dual_gate_sweep"
    assert metadata["points_written"] == 12
    assert (run_dirs[0] / "dual_gate_heatmap.svg").exists()
    assert (run_dirs[0] / "dual_gate_report.md").exists()
    assert (run_dirs[0] / "dual_gate_stats.csv").exists()
    assert (tmp_path / "index.jsonl").exists()


def test_cli_dual_gate_hardware_run_is_blocked(tmp_path):
    recipe = write_dual_gate_cli_recipe(tmp_path)

    code = cli.main(["dual-gate", str(recipe)])

    assert code == 2
    assert not (tmp_path / "raw").exists()
