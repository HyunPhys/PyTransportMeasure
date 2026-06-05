import csv
import json
from pathlib import Path

from pytransport import cli
from pytransport.dual_gate_lockin_review import audit_dual_gate_lockin_run
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
  reference_source: internal
  reference_frequency_hz: 17.777
  sine_output_amplitude_v: 0.01
  input_mode: voltage
  voltage_input: a
  input_coupling: ac
  input_grounding: float
  voltage_input_range_v: 0.01
  sensitivity_index: 18
  time_constant_index: 10
  filter_slope_db_per_oct: 24
  synchronous_filter: false
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


def make_strictly_accepted_previous_run(tmp_path: Path) -> Path:
    previous_root = tmp_path / "previous"
    previous_root.mkdir()
    recipe = write_dual_gate_lockin_cli_recipe(previous_root)
    code = cli.main(
        [
            "dual-gate-lockin",
            str(recipe),
            "--dry-run",
            "--fake-noise-std",
            "0",
            "--index-path",
            str(previous_root / "previous_index.jsonl"),
        ]
    )
    assert code == 0
    run_dir = list((previous_root / "raw").glob("*dual_gate_lockin_cli"))[0]
    metadata_path = run_dir / "metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    probe = metadata.setdefault("lockin_probe", {})
    probe.update(
        {
            "error_status": "0",
            "lia_status": "0",
            "setting_reference_source": "0",
            "setting_reference_frequency_hz": "17.777",
            "setting_sine_output_amplitude_v": "0.01",
            "setting_input_mode": "0",
            "setting_voltage_input": "0",
            "setting_input_coupling": "0",
            "setting_input_grounding": "0",
            "setting_voltage_input_range_v": "4",
            "setting_sensitivity_index": "18",
            "setting_time_constant_index": "10",
            "setting_filter_slope_index": "3",
            "setting_synchronous_filter": "0",
        }
    )
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")
    audit = audit_dual_gate_lockin_run(run_dir, require_lockin_settings=True)
    assert audit.accepted
    return run_dir


def force_gate1_leakage_margin_warning(run_dir: Path) -> None:
    points_path = run_dir / "points.csv"
    with points_path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])
    assert rows
    for row in rows:
        row["gate1_current_a"] = "2.0e-9"
    with points_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    audit = audit_dual_gate_lockin_run(run_dir, require_lockin_settings=True)
    assert audit.accepted
    assert any(issue.check == "gate1_leakage_margin" and issue.severity == "warning" for issue in audit.issues)


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


def test_cli_dual_gate_lockin_resume_from_partial_run(tmp_path):
    recipe = write_dual_gate_lockin_cli_recipe(tmp_path)
    code = cli.main(
        [
            "dual-gate-lockin",
            str(recipe),
            "--dry-run",
            "--fake-noise-std",
            "0",
            "--index-path",
            str(tmp_path / "index.jsonl"),
        ]
    )
    assert code == 0
    source_run_dir = list((tmp_path / "raw").glob("*dual_gate_lockin_cli"))[0]
    points_path = source_run_dir / "points.csv"
    with points_path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])
    with points_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows[:2])
    metadata_path = source_run_dir / "metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata.update({"completed": False, "abort_class": "interrupted", "points_written": 2, "remaining_points": 2})
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")

    code = cli.main(
        [
            "dual-gate-lockin",
            str(recipe),
            "--dry-run",
            "--resume-from-run",
            str(source_run_dir),
            "--fake-noise-std",
            "0",
            "--index-path",
            str(tmp_path / "index.jsonl"),
        ]
    )

    assert code == 0
    run_dirs = sorted((tmp_path / "raw").glob("*dual_gate_lockin_cli*"))
    assert len(run_dirs) == 2
    resumed_metadata = json.loads((run_dirs[-1] / "metadata.json").read_text(encoding="utf-8"))
    assert resumed_metadata["completed"] is True
    assert resumed_metadata["points_written"] == 4
    assert resumed_metadata["points_copied_from_resume"] == 2
    assert resumed_metadata["points_measured_this_run"] == 2
    assert resumed_metadata["resume_from_run"] == str(source_run_dir)


def test_cli_dual_gate_lockin_resume_check(tmp_path):
    recipe = write_dual_gate_lockin_cli_recipe(tmp_path)
    code = cli.main(
        [
            "dual-gate-lockin",
            str(recipe),
            "--dry-run",
            "--fake-noise-std",
            "0",
            "--index-path",
            str(tmp_path / "index.jsonl"),
        ]
    )
    assert code == 0
    run_dir = list((tmp_path / "raw").glob("*dual_gate_lockin_cli"))[0]
    points_path = run_dir / "points.csv"
    with points_path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])
    with points_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows[:2])
    metadata_path = run_dir / "metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata.update({"completed": False, "points_written": 2, "remaining_points": 2})
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")

    assert cli.main(["dual-gate-lockin-resume-check", str(recipe), str(run_dir)]) == 0


def test_cli_dual_gate_lockin_resume_check_fails_for_completed_run(tmp_path):
    recipe = write_dual_gate_lockin_cli_recipe(tmp_path)
    code = cli.main(
        [
            "dual-gate-lockin",
            str(recipe),
            "--dry-run",
            "--fake-noise-std",
            "0",
            "--index-path",
            str(tmp_path / "index.jsonl"),
        ]
    )
    assert code == 0
    run_dir = list((tmp_path / "raw").glob("*dual_gate_lockin_cli"))[0]

    assert cli.main(["dual-gate-lockin-resume-check", str(recipe), str(run_dir)]) == 2


def test_cli_dual_gate_lockin_audit_saved_run(tmp_path):
    recipe = write_dual_gate_lockin_cli_recipe(tmp_path)
    code = cli.main(
        [
            "dual-gate-lockin",
            str(recipe),
            "--dry-run",
            "--fake-noise-std",
            "0",
            "--index-path",
            str(tmp_path / "index.jsonl"),
        ]
    )
    assert code == 0
    run_dir = list((tmp_path / "raw").glob("*dual_gate_lockin_cli"))[0]

    strict_code = cli.main(["dual-gate-lockin-audit", str(run_dir)])
    relaxed_code = cli.main(
        [
            "dual-gate-lockin-audit",
            str(run_dir),
            "--allow-missing-lockin-settings",
            "--write-report",
        ]
    )

    assert strict_code == 2
    assert relaxed_code == 0
    assert (run_dir / "dual_gate_lockin_acceptance.md").exists()


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


def test_cli_dual_gate_lockin_checkpoint_allows_small_hardware_invocation(tmp_path, monkeypatch):
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
            "1",
            "--stop-after-new-points",
            "1",
            "--yes",
            "--index-path",
            str(tmp_path / "index.jsonl"),
        ]
    )

    assert code == 0
    run_dir = list((tmp_path / "raw").glob("*dual_gate_lockin_cli"))[0]
    metadata = json.loads((run_dir / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["abort_class"] == "checkpoint"
    assert metadata["points_written"] == 1
    assert metadata["checkpoint_reached"] is True
    assert metadata["hardware_guard"]["recipe_points"] == 4
    assert metadata["hardware_guard"]["hardware_points_for_this_invocation"] == 1
    assert metadata["hardware_guard"]["stop_after_new_points"] == 1
    assert gate1.is_output_on is False
    assert gate2.is_output_on is False


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


def test_cli_dual_gate_lockin_blocks_raised_point_guard_without_previous_acceptance(tmp_path):
    recipe = write_dual_gate_lockin_cli_recipe(tmp_path)

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

    assert code == 2
    assert not (tmp_path / "raw").exists()


def test_cli_dual_gate_lockin_records_raised_point_guard_note(tmp_path, monkeypatch):
    previous_run = make_strictly_accepted_previous_run(tmp_path)
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
            "--accepted-previous-run",
            str(previous_run),
            "--yes",
        ]
    )

    assert code == 0
    run_dirs = sorted((tmp_path / "raw").glob("*dual_gate_lockin_cli"))
    metadata = json.loads((run_dirs[-1] / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["hardware_guard"]["requested_max_hardware_points"] == 12
    assert metadata["hardware_guard"]["raised_above_default"] is True
    assert metadata["hardware_guard"]["approval_note"] == "limited lab feedback ok"
    assert metadata["hardware_guard"]["accepted_previous_run"] == str(previous_run)
    assert metadata["hardware_guard"]["accepted_previous_run_audit_passed"] is True
    assert metadata["hardware_guard"]["accepted_previous_run_points_written"] == 4
    assert metadata["hardware_guard"]["accepted_previous_run_scale_up_compatible"] is True
    assert metadata["hardware_guard"]["accepted_previous_run_grid_signature"]


def test_cli_dual_gate_lockin_blocks_raised_guard_when_previous_grid_not_in_candidate(tmp_path):
    previous_run = make_strictly_accepted_previous_run(tmp_path)
    recipe = write_dual_gate_lockin_cli_recipe(tmp_path)
    text = recipe.read_text(encoding="utf-8")
    text = text.replace("  start_v: -0.1\n  stop_v: 0.1\n", "  start_v: -0.2\n  stop_v: 0.2\n", 1)
    recipe.write_text(text, encoding="utf-8")

    code = cli.main(
        [
            "dual-gate-lockin",
            str(recipe),
            "--allow-active-sweep",
            "--max-hardware-points",
            "12",
            "--hardware-approval-note",
            "limited lab feedback ok",
            "--accepted-previous-run",
            str(previous_run),
            "--yes",
        ]
    )

    assert code == 2
    assert not (tmp_path / "raw").exists()


def test_cli_dual_gate_lockin_blocks_raised_guard_when_previous_leakage_margin_is_small(tmp_path):
    previous_run = make_strictly_accepted_previous_run(tmp_path)
    force_gate1_leakage_margin_warning(previous_run)
    recipe = write_dual_gate_lockin_cli_recipe(tmp_path)

    code = cli.main(
        [
            "dual-gate-lockin",
            str(recipe),
            "--allow-active-sweep",
            "--max-hardware-points",
            "12",
            "--hardware-approval-note",
            "limited lab feedback ok",
            "--accepted-previous-run",
            str(previous_run),
            "--yes",
        ]
    )

    assert code == 2
    assert not (tmp_path / "raw").exists()


def test_cli_dual_gate_lockin_scale_up_check_passes_for_compatible_candidate(tmp_path):
    previous_run = make_strictly_accepted_previous_run(tmp_path)
    recipe = write_dual_gate_lockin_cli_recipe(tmp_path)

    code = cli.main(["dual-gate-lockin-scale-up-check", str(previous_run), str(recipe)])

    assert code == 0


def test_cli_dual_gate_lockin_scale_up_check_fails_for_incompatible_candidate(tmp_path):
    previous_run = make_strictly_accepted_previous_run(tmp_path)
    recipe = write_dual_gate_lockin_cli_recipe(tmp_path)
    text = recipe.read_text(encoding="utf-8")
    text = text.replace("  input_grounding: float\n", "  input_grounding: ground\n")
    recipe.write_text(text, encoding="utf-8")

    code = cli.main(["dual-gate-lockin-scale-up-check", str(previous_run), str(recipe)])

    assert code == 2


def test_cli_dual_gate_lockin_scale_up_check_fails_for_leakage_margin_warning(tmp_path):
    previous_run = make_strictly_accepted_previous_run(tmp_path)
    force_gate1_leakage_margin_warning(previous_run)
    recipe = write_dual_gate_lockin_cli_recipe(tmp_path)

    code = cli.main(["dual-gate-lockin-scale-up-check", str(previous_run), str(recipe)])

    assert code == 2


def test_cli_dual_gate_lockin_scale_up_template_writes_compatible_candidate(tmp_path):
    previous_run = make_strictly_accepted_previous_run(tmp_path)
    output_recipe = tmp_path / "candidate_broader.yaml"

    code = cli.main(
        [
            "dual-gate-lockin-scale-up-template",
            str(previous_run),
            str(output_recipe),
            "--gate1-start-v",
            "-0.1",
            "--gate1-stop-v",
            "0.1",
            "--gate1-points",
            "3",
            "--gate2-start-v",
            "-0.1",
            "--gate2-stop-v",
            "0.1",
            "--gate2-points",
            "3",
            "--measurement-name",
            "broader_candidate",
            "--output-directory",
            str(tmp_path / "raw_broader"),
        ]
    )

    assert code == 0
    text = output_recipe.read_text(encoding="utf-8")
    assert "measurement_name: broader_candidate" in text
    assert "directory: " in text
    assert "points: 3" in text
    review = output_recipe.with_suffix(".review.md")
    assert review.exists()
    review_text = review.read_text(encoding="utf-8")
    assert "Dual-Gate Lock-In Scale-Up Review" in review_text
    assert "ptm dual-gate-lockin-scale-up-check" in review_text
    assert "ptm dual-gate-lockin-preflight" in review_text
    assert "--accepted-previous-run" in review_text
    assert "Candidate points: 9" in review_text


def test_cli_dual_gate_lockin_scale_up_template_fails_when_grid_does_not_include_previous(tmp_path):
    previous_run = make_strictly_accepted_previous_run(tmp_path)
    output_recipe = tmp_path / "candidate_bad.yaml"

    code = cli.main(
        [
            "dual-gate-lockin-scale-up-template",
            str(previous_run),
            str(output_recipe),
            "--gate1-start-v",
            "-0.2",
            "--gate1-stop-v",
            "0.2",
            "--gate1-points",
            "3",
            "--gate2-start-v",
            "-0.2",
            "--gate2-stop-v",
            "0.2",
            "--gate2-points",
            "3",
        ]
    )

    assert code == 2
    assert output_recipe.exists()


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


def test_cli_dual_gate_lockin_chunk_plan(tmp_path):
    recipe = write_dual_gate_lockin_cli_recipe(tmp_path)

    code = cli.main(
        [
            "dual-gate-lockin-chunk-plan",
            str(recipe),
            "--chunk-size",
            "2",
            "--max-hardware-points",
            "2",
        ]
    )

    assert code == 0


def test_cli_dual_gate_lockin_chunk_plan_fails_when_chunk_exceeds_guard(tmp_path):
    recipe = write_dual_gate_lockin_cli_recipe(tmp_path)

    code = cli.main(
        [
            "dual-gate-lockin-chunk-plan",
            str(recipe),
            "--chunk-size",
            "3",
            "--max-hardware-points",
            "2",
        ]
    )

    assert code == 2


def test_cli_dual_gate_lockin_stitch_chunks(tmp_path):
    recipe = write_dual_gate_lockin_cli_recipe(tmp_path)
    index_path = tmp_path / "index.jsonl"
    code = cli.main(
        [
            "dual-gate-lockin",
            str(recipe),
            "--dry-run",
            "--stop-after-new-points",
            "2",
            "--fake-noise-std",
            "0",
            "--index-path",
            str(index_path),
        ]
    )
    assert code == 0
    chunk1 = sorted((tmp_path / "raw").glob("*dual_gate_lockin_cli"))[-1]
    code = cli.main(
        [
            "dual-gate-lockin",
            str(recipe),
            "--dry-run",
            "--resume-from-run",
            str(chunk1),
            "--fake-noise-std",
            "0",
            "--index-path",
            str(index_path),
        ]
    )
    assert code == 0
    chunk2 = sorted((tmp_path / "raw").glob("*dual_gate_lockin_cli*"))[-1]

    code = cli.main(
        [
            "dual-gate-lockin-stitch-chunks",
            str(chunk1),
            str(chunk2),
            "--output-dir",
            str(tmp_path / "stitched"),
            "--measurement-name",
            "cli_stitched",
            "--gate-stats",
            "--plot",
            "--report",
            "--index-path",
            str(index_path),
        ]
    )

    assert code == 0
    stitched = list((tmp_path / "stitched").glob("*cli_stitched"))[0]
    metadata = json.loads((stitched / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["completed"] is True
    assert metadata["stitched_from_chunks"] is True
    assert metadata["points_written"] == 4
    assert (stitched / "dual_gate_lockin_stats.csv").exists()
    assert (stitched / "dual_gate_lockin_heatmap.svg").exists()
    assert (stitched / "dual_gate_lockin_report.md").exists()


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
