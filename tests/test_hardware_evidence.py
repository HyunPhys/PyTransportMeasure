import json
from pathlib import Path

from pytransport import cli
from pytransport.hardware_evidence import audit_hardware_evidence, format_hardware_evidence_audit


def write_ac_recipe(tmp_path: Path) -> Path:
    recipe = tmp_path / "ac_recipe.yaml"
    output_dir = str(tmp_path / "raw").replace("\\", "/")
    recipe.write_text(
        f"""
measurement_name: evidence_ac
safety_preset: nano_device_safe
measurement_geometry:
  terminal_count: 4
  method: four_terminal
source_instrument:
  id: keithley_2450
  address: GPIB0::2::INSTR
  voltage_range_v: 0.02
  current_range_a: 1.0e-7
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
  lockin_input_contacts: [Vxx+, Vxx-]
  excitation_contacts: [S, D]
bias_sweep:
  start_v: -0.001
  stop_v: 0.001
  points: 3
  delay_s: 0
  current_compliance_a: 1.0e-7
output:
  directory: {output_dir}
""".strip(),
        encoding="utf-8",
    )
    return recipe


def write_run_metadata(tmp_path: Path, recipe: Path, audit_json: Path | None) -> Path:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    metadata = {
        "measurement_type": "ac_lockin_sweep",
        "recipe_path": str(recipe),
        "metadata_path": str(run_dir / "metadata.json"),
        "completed": True,
        "dry_run": False,
    }
    if audit_json is not None:
        metadata["hardware_evidence"] = {
            "schema": "pytransport.hardware_evidence.v1",
            "measurement_audit_json": str(audit_json),
            "measurement_audit_evidence_passed": True,
            "sr860_configure_json": None,
            "sr860_configure_evidence_passed": False,
            "preflight_reran_after_evidence_check": True,
        }
    (run_dir / "metadata.json").write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")
    return run_dir


def test_hardware_evidence_audit_accepts_matching_measurement_audit(tmp_path: Path):
    recipe = write_ac_recipe(tmp_path)
    audit_json = tmp_path / "measurement_audit.json"
    assert cli.main(["measurement-parameter-audit", "ac_lockin_sweep", str(recipe), "--json-output", str(audit_json)]) == 0
    run_dir = write_run_metadata(tmp_path, recipe, audit_json)

    audit = audit_hardware_evidence(run_dir, require_measurement_audit=True)
    text = format_hardware_evidence_audit(audit)

    assert audit.accepted is True
    assert audit.measurement_audit_check is not None
    assert audit.measurement_audit_check["ok"] is True
    assert "Hardware evidence audit: PASS" in text


def test_hardware_evidence_audit_fails_when_recipe_drifts_from_saved_audit(tmp_path: Path):
    recipe = write_ac_recipe(tmp_path)
    audit_json = tmp_path / "measurement_audit.json"
    assert cli.main(["measurement-parameter-audit", "ac_lockin_sweep", str(recipe), "--json-output", str(audit_json)]) == 0
    recipe.write_text(recipe.read_text(encoding="utf-8").replace("  nplc: 1.0\n", "  nplc: 3.0\n"), encoding="utf-8")
    run_dir = write_run_metadata(tmp_path, recipe, audit_json)

    audit = audit_hardware_evidence(run_dir, require_measurement_audit=True)

    assert audit.accepted is False
    assert any(issue.check == "measurement_audit_recheck" and issue.severity == "error" for issue in audit.issues)


def test_hardware_evidence_audit_missing_block_is_warning_unless_required(tmp_path: Path):
    recipe = write_ac_recipe(tmp_path)
    run_dir = write_run_metadata(tmp_path, recipe, None)

    relaxed = audit_hardware_evidence(run_dir)
    strict = audit_hardware_evidence(run_dir, require_measurement_audit=True)

    assert relaxed.accepted is True
    assert relaxed.issues[0].severity == "warning"
    assert strict.accepted is False
    assert strict.issues[0].severity == "error"


def test_cli_hardware_evidence_audit_writes_json(tmp_path: Path):
    recipe = write_ac_recipe(tmp_path)
    audit_json = tmp_path / "measurement_audit.json"
    output = tmp_path / "hardware_evidence_audit.json"
    assert cli.main(["measurement-parameter-audit", "ac_lockin_sweep", str(recipe), "--json-output", str(audit_json)]) == 0
    run_dir = write_run_metadata(tmp_path, recipe, audit_json)

    code = cli.main(
        [
            "hardware-evidence-audit",
            str(run_dir),
            "--require-measurement-audit",
            "--json-output",
            str(output),
        ]
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert code == 0
    assert payload["accepted"] is True
    assert payload["measurement_audit_check"]["ok"] is True
