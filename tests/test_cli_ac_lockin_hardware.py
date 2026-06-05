from pathlib import Path

from pytransport import cli
from pytransport.instruments.fake import FakeLockIn, FakeSMU
from pytransport.preflight import AcLockInPreflightReport, InstrumentPreflight


def write_ac_lockin_cli_recipe(tmp_path: Path) -> Path:
    recipe = tmp_path / "ac_lockin_cli.yaml"
    output_dir = str(tmp_path / "raw").replace("\\", "/")
    recipe.write_text(
        f"""
measurement_name: ac_lockin_cli_hardware
safety_preset: nano_device_safe
source_instrument:
  id: keithley_2450
  address: GPIB0::2::INSTR
  timeout_ms: 10000
  terminal: FRONT
  voltage_range_v: 0.02
  current_range_a: 1.0e-7
  nplc: 1.0
lockin:
  enabled: true
  id: srs_sr860
  address: GPIB0::4::INSTR
  timeout_ms: 10000
  channels: [x, y, r, theta]
  read_timing: after_dc_settle
bias_sweep:
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


def passing_ac_preflight(recipe_path, safety_dir):
    return AcLockInPreflightReport(
        recipe_path=str(recipe_path),
        validation_ok=True,
        validation_error=None,
        visa_resources=("GPIB0::2::INSTR", "GPIB0::4::INSTR"),
        distinct_addresses=True,
        source=InstrumentPreflight(
            label="source",
            address="GPIB0::2::INSTR",
            address_found=True,
            probe={"idn": "KEITHLEY INSTRUMENTS,MODEL 2450,123,1.0"},
            probe_error=None,
        ),
        lockin=InstrumentPreflight(
            label="lock-in",
            address="GPIB0::4::INSTR",
            address_found=True,
            probe={"idn": "Stanford_Research_Systems,SR860,000111,v1.23", "error_status": "0", "lia_status": "0"},
            probe_error=None,
        ),
    )


def failing_ac_preflight(recipe_path, safety_dir):
    report = passing_ac_preflight(recipe_path, safety_dir)
    return AcLockInPreflightReport(
        recipe_path=report.recipe_path,
        validation_ok=True,
        validation_error=None,
        visa_resources=("GPIB0::2::INSTR",),
        distinct_addresses=True,
        source=report.source,
        lockin=InstrumentPreflight(
            label="lock-in",
            address="GPIB0::4::INSTR",
            address_found=False,
            probe=None,
            probe_error=None,
        ),
    )


def test_cli_ac_lockin_hardware_run_uses_real_instrument_factories_after_preflight(tmp_path, monkeypatch):
    recipe = write_ac_lockin_cli_recipe(tmp_path)
    source = FakeSMU(resistance_ohm=1_000_000, noise_std_a=0)
    lockin = FakeLockIn(signal_r_v=2e-6, phase_deg=30, noise_std_v=0)

    monkeypatch.setattr(cli, "run_ac_lockin_preflight", passing_ac_preflight)
    monkeypatch.setattr(cli, "Keithley2450", lambda address, timeout_ms: source)
    monkeypatch.setattr(cli, "SRS_SR860", lambda address, timeout_ms: lockin)

    code = cli.main(
        [
            "ac-lockin",
            str(recipe),
            "--yes",
            "--summary",
            "--plot",
            "--report",
            "--index-path",
            str(tmp_path / "index.jsonl"),
        ]
    )

    assert code == 0
    assert source.is_output_on is False
    assert lockin.connected is False
    run_dirs = list((tmp_path / "raw").glob("*ac_lockin_cli_hardware"))
    assert len(run_dirs) == 1
    assert (run_dirs[0] / "points.csv").exists()
    assert (run_dirs[0] / "metadata.json").exists()
    assert (run_dirs[0] / "ac_lockin_plot.svg").exists()
    assert (run_dirs[0] / "ac_lockin_report.md").exists()


def test_cli_ac_lockin_hardware_run_blocks_when_preflight_fails(tmp_path, monkeypatch):
    recipe = write_ac_lockin_cli_recipe(tmp_path)

    monkeypatch.setattr(cli, "run_ac_lockin_preflight", failing_ac_preflight)

    code = cli.main(["ac-lockin", str(recipe), "--yes"])

    assert code == 2
    assert not (tmp_path / "raw").exists()


def test_cli_ac_lockin_hardware_run_requires_source_smu_parameters(tmp_path, monkeypatch):
    recipe = write_ac_lockin_cli_recipe(tmp_path)
    text = recipe.read_text(encoding="utf-8").replace("  nplc: 1.0\n", "").replace("  current_range_a: 1.0e-7\n", "")
    recipe.write_text(text, encoding="utf-8")
    monkeypatch.setattr(cli, "run_ac_lockin_preflight", passing_ac_preflight)

    code = cli.main(["ac-lockin", str(recipe), "--yes"])

    assert code == 2
    assert not (tmp_path / "raw").exists()


def test_cli_ac_lockin_dry_run_allows_missing_source_smu_parameters(tmp_path):
    recipe = write_ac_lockin_cli_recipe(tmp_path)
    text = recipe.read_text(encoding="utf-8").replace("  nplc: 1.0\n", "").replace("  current_range_a: 1.0e-7\n", "")
    recipe.write_text(text, encoding="utf-8")

    code = cli.main(
        [
            "ac-lockin",
            str(recipe),
            "--dry-run",
            "--fake-noise-std",
            "0",
            "--index-path",
            str(tmp_path / "index.jsonl"),
        ]
    )

    assert code == 0
    assert len(list((tmp_path / "raw").glob("*ac_lockin_cli_hardware"))) == 1
