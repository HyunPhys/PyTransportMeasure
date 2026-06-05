from pathlib import Path

from pytransport import cli
from pytransport.instruments.fake import FakeSMU


def write_drain_cli_recipe(tmp_path: Path) -> Path:
    recipe = tmp_path / "drain_iv_cli.yaml"
    output_dir = str(tmp_path / "raw").replace("\\", "/")
    recipe.write_text(
        f"""
measurement_name: drain_iv_cli_hardware
safety_preset: nano_device_safe
instrument:
  id: keithley_2450
  address: GPIB0::2::INSTR
  timeout_ms: 10000
  terminal: FRONT
  voltage_range_v: 0.02
  current_range_a: 1.0e-7
  nplc: 1.0
sweep:
  mode: linear_one_way
  start_v: -0.001
  stop_v: 0.001
  points: 3
  delay_s: 0
  current_compliance_a: 1.0e-7
output:
  directory: {output_dir}
checks:
  require_completed: true
  min_points: 3
""".strip(),
        encoding="utf-8",
    )
    return recipe


def test_cli_drain_hardware_run_requires_keithley_measurement_parameters(tmp_path, monkeypatch):
    recipe = write_drain_cli_recipe(tmp_path)
    text = (
        recipe.read_text(encoding="utf-8")
        .replace("  nplc: 1.0\n", "")
        .replace("  current_range_a: 1.0e-7\n", "")
    )
    recipe.write_text(text, encoding="utf-8")

    def fail_if_preflight_runs(*args, **kwargs):
        raise AssertionError("preflight should not run before required Keithley parameters pass")

    monkeypatch.setattr(cli, "run_preflight", fail_if_preflight_runs)

    code = cli.main(["run", str(recipe), "--yes"])

    assert code == 2
    assert not (tmp_path / "raw").exists()


def test_cli_drain_dry_run_allows_missing_keithley_measurement_parameters(tmp_path):
    recipe = write_drain_cli_recipe(tmp_path)
    text = (
        recipe.read_text(encoding="utf-8")
        .replace("  nplc: 1.0\n", "")
        .replace("  current_range_a: 1.0e-7\n", "")
    )
    recipe.write_text(text, encoding="utf-8")

    code = cli.main(
        [
            "run",
            str(recipe),
            "--dry-run",
            "--fake-noise-std",
            "0",
            "--index-path",
            str(tmp_path / "index.jsonl"),
        ]
    )

    assert code == 0
    assert len(list((tmp_path / "raw").glob("*drain_iv_cli_hardware"))) == 1


def test_cli_drain_hardware_run_passes_explicit_nplc_to_keithley_config(tmp_path, monkeypatch):
    recipe = write_drain_cli_recipe(tmp_path)
    smu = FakeSMU(resistance_ohm=1_000_000, noise_std_a=0)

    class PassingPreflight:
        ok = True

    monkeypatch.setattr(cli, "run_preflight", lambda *args, **kwargs: PassingPreflight())
    monkeypatch.setattr(cli, "format_preflight_report", lambda report: "preflight ok")
    monkeypatch.setattr(cli, "Keithley2450", lambda address, timeout_ms: smu)

    code = cli.main(
        [
            "run",
            str(recipe),
            "--yes",
            "--index-path",
            str(tmp_path / "index.jsonl"),
        ]
    )

    assert code == 0
    assert smu.last_voltage_source_config is not None
    assert smu.last_voltage_source_config.nplc == 1.0
    assert smu.last_voltage_source_config.voltage_range_v == 0.02
    assert smu.last_voltage_source_config.current_range_a == 1.0e-7
