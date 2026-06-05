import csv
import json
from pathlib import Path
import zipfile

import yaml

from pytransport.cli import main
from pytransport.dual_gate_lockin import run_dual_gate_lockin_sweep
from pytransport.dual_gate_lockin_hall_suite import (
    audit_dual_gate_lockin_hall_suite,
    format_dual_gate_lockin_hall_suite_chunk_workflow_plan,
    format_dual_gate_lockin_hall_suite_plan,
    write_dual_gate_lockin_hall_suite_template,
)
from pytransport.instruments.fake import DualGateFakeDeviceState, DualGateFakeLockIn, DualGateFakeSMU
from pytransport.recipes import load_dual_gate_lockin_recipe, load_named_safety_preset


def run_hall_suite_recipe_dry(recipe_path):
    recipe = load_dual_gate_lockin_recipe(recipe_path)
    safety = load_named_safety_preset(recipe.safety_preset)
    state = DualGateFakeDeviceState(
        gate1_leak_resistance_ohm=1_000_000_000.0,
        gate2_leak_resistance_ohm=1_000_000_000.0,
    )
    gate1 = DualGateFakeSMU("gate1", state)
    gate2 = DualGateFakeSMU("gate2", state)
    lockin = DualGateFakeLockIn(state, base_r_v=2e-6, phase_deg=0, noise_std_v=0)
    metadata = run_dual_gate_lockin_sweep(recipe, safety, gate1, gate2, lockin, recipe_path=recipe_path)
    return metadata["run_dir"]


def shrink_hall_suite_for_intake_tests(result):
    for path in [
        result.longitudinal_recipe,
        result.plus_hall_recipe,
        result.minus_hall_recipe,
        result.zero_hall_recipe,
    ]:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        data["gate1_sweep"]["points"] = 2
        data["gate2_sweep"]["points"] = 2
        data["gate1_sweep"]["settle_s"] = 0.0
        data["gate2_sweep"]["settle_s"] = 0.0
        data["lockin"]["read_settle_s"] = 0.0
        path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def test_write_hall_suite_template_creates_valid_recipe_set(tmp_path):
    result = write_dual_gate_lockin_hall_suite_template(
        "configs/recipes/dual_gate_lockin_four_terminal_dry_run.yaml",
        tmp_path / "suite",
        measurement_prefix="graphene_a",
        magnetic_field_t=1.5,
        longitudinal_contacts=["Vxx+", "Vxx-"],
        hall_contacts=["Vxy+", "Vxy-"],
        channel_length_m=4e-6,
        channel_width_m=2e-6,
        run_output_directory=tmp_path / "raw",
    )

    longitudinal = load_dual_gate_lockin_recipe(result.longitudinal_recipe)
    plus = load_dual_gate_lockin_recipe(result.plus_hall_recipe)
    minus = load_dual_gate_lockin_recipe(result.minus_hall_recipe)
    zero = load_dual_gate_lockin_recipe(result.zero_hall_recipe)

    assert longitudinal.measurement_name == "graphene_a_vxx"
    assert longitudinal.topology.voltage_probe_role == "longitudinal"
    assert longitudinal.topology.lockin_input_contacts == ["Vxx+", "Vxx-"]
    assert longitudinal.topology.channel_length_m == 4e-6
    assert longitudinal.topology.channel_width_m == 2e-6
    assert longitudinal.output.directory == tmp_path / "raw"
    assert plus.measurement_name == "graphene_a_vxy_plus_b"
    assert plus.topology.voltage_probe_role == "hall"
    assert plus.topology.lockin_input_contacts == ["Vxy+", "Vxy-"]
    assert plus.topology.magnetic_field_t == 1.5
    assert plus.topology.channel_length_m is None
    assert minus.topology.magnetic_field_t == -1.5
    assert zero.topology.magnetic_field_t == 0.0
    review = result.review_path.read_text(encoding="utf-8")
    assert "dual-gate-lockin-hall-suite-check" in review
    assert "dual-gate-lockin-hall-suite-plan" in review
    assert "dual-gate-lockin-hall-suite-chunk-plan" in review
    assert "dual-gate-lockin-hall-antisym" in review
    assert "dual-gate-lockin-hall-mobility" in review

    audit = audit_dual_gate_lockin_hall_suite(
        result.longitudinal_recipe,
        result.plus_hall_recipe,
        result.minus_hall_recipe,
        zero_hall_recipe=result.zero_hall_recipe,
    )
    assert audit.compatible is True
    assert audit.point_count == 25


def test_hall_suite_template_can_skip_zero_field(tmp_path):
    result = write_dual_gate_lockin_hall_suite_template(
        "configs/recipes/dual_gate_lockin_four_terminal_dry_run.yaml",
        tmp_path / "suite",
        measurement_prefix="graphene_no_zero",
        magnetic_field_t=1.0,
        include_zero_field=False,
    )

    assert result.zero_hall_recipe is None
    files = {path.name for path in result.output_dir.iterdir()}
    assert "graphene_no_zero_vxy_zero_b.yaml" not in files
    assert "graphene_no_zero_vxy_plus_b.yaml" in files


def test_cli_dual_gate_lockin_hall_suite_template(tmp_path):
    output = tmp_path / "suite"

    code = main(
        [
            "dual-gate-lockin-hall-suite-template",
            "configs/recipes/dual_gate_lockin_four_terminal_dry_run.yaml",
            str(output),
            "--measurement-prefix",
            "cli_graphene",
            "--magnetic-field-t",
            "2.0",
            "--longitudinal-contact",
            "V1",
            "--longitudinal-contact",
            "V2",
            "--hall-contact",
            "VH1",
            "--hall-contact",
            "VH2",
        ]
    )

    assert code == 0
    assert (output / "cli_graphene_vxx.yaml").exists()
    assert (output / "cli_graphene_vxy_plus_b.yaml").exists()
    assert (output / "cli_graphene_vxy_minus_b.yaml").exists()
    assert (output / "cli_graphene_vxy_zero_b.yaml").exists()
    data = yaml.safe_load((output / "cli_graphene_vxy_plus_b.yaml").read_text(encoding="utf-8"))
    assert data["topology"]["lockin_input_contacts"] == ["VH1", "VH2"]

    code = main(
        [
            "dual-gate-lockin-hall-suite-check",
            str(output / "cli_graphene_vxx.yaml"),
            str(output / "cli_graphene_vxy_plus_b.yaml"),
            str(output / "cli_graphene_vxy_minus_b.yaml"),
            "--zero-field-recipe",
            str(output / "cli_graphene_vxy_zero_b.yaml"),
        ]
    )
    assert code == 0

    code = main(
        [
            "dual-gate-lockin-hall-suite-plan",
            str(output / "cli_graphene_vxx.yaml"),
            str(output / "cli_graphene_vxy_plus_b.yaml"),
            str(output / "cli_graphene_vxy_minus_b.yaml"),
            "--zero-field-recipe",
            str(output / "cli_graphene_vxy_zero_b.yaml"),
            "--preview-points",
            "2",
        ]
    )
    assert code == 0

    code = main(
        [
            "dual-gate-lockin-hall-suite-chunk-plan",
            str(output / "cli_graphene_vxx.yaml"),
            str(output / "cli_graphene_vxy_plus_b.yaml"),
            str(output / "cli_graphene_vxy_minus_b.yaml"),
            "--zero-field-recipe",
            str(output / "cli_graphene_vxy_zero_b.yaml"),
            "--chunk-size",
            "2",
        ]
    )
    assert code == 0


def test_hall_suite_plan_formats_aggregate_runbook(tmp_path):
    result = write_dual_gate_lockin_hall_suite_template(
        "configs/recipes/dual_gate_lockin_four_terminal_dry_run.yaml",
        tmp_path / "suite",
        measurement_prefix="plan_graphene",
        magnetic_field_t=1.0,
    )

    plan = format_dual_gate_lockin_hall_suite_plan(
        result.longitudinal_recipe,
        result.plus_hall_recipe,
        result.minus_hall_recipe,
        zero_hall_recipe=result.zero_hall_recipe,
        preview_points=2,
    )

    assert "Dual-Gate Lock-In Hall Suite Plan" in plan
    assert "Dual-gate lock-in Hall suite consistency: PASS" in plan
    assert "Measurement Order" in plan
    assert "plan_graphene_vxx" in plan
    assert "plan_graphene_vxy_plus_b" in plan
    assert "dual-gate-lockin-hall-suite-check" in plan
    assert "dual-gate-lockin-preflight" in plan
    assert "dual-gate-lockin-hall-antisym" in plan
    assert "dual-gate-lockin-hall-zero-correct" in plan
    assert "dual-gate-lockin-hall-mobility" in plan
    assert "Plan Snapshots" in plan


def test_hall_suite_chunk_workflow_plan_formats_chunk_and_stitch_commands(tmp_path):
    result = write_dual_gate_lockin_hall_suite_template(
        "configs/recipes/dual_gate_lockin_four_terminal_dry_run.yaml",
        tmp_path / "suite",
        measurement_prefix="chunk_graphene",
        magnetic_field_t=1.0,
    )

    plan = format_dual_gate_lockin_hall_suite_chunk_workflow_plan(
        result.longitudinal_recipe,
        result.plus_hall_recipe,
        result.minus_hall_recipe,
        zero_hall_recipe=result.zero_hall_recipe,
        chunk_size=4,
        max_hardware_points=4,
    )

    assert "Dual-Gate Lock-In Hall Suite Chunk Workflow" in plan
    assert "Chunks per recipe: 7" in plan
    assert "dual-gate-lockin-chunk-plan" in plan
    assert "dual-gate-lockin-stitch-chunks" in plan
    assert "chunk_graphene_vxx_stitched" in plan
    assert "chunk_graphene_vxy_plus_b_stitched" in plan
    assert "dual-gate-lockin-hall-antisym" in plan
    assert "dual-gate-lockin-hall-zero-correct" in plan
    assert "dual-gate-lockin-hall-mobility" in plan


def test_hall_suite_check_fails_for_mismatched_field(tmp_path):
    result = write_dual_gate_lockin_hall_suite_template(
        "configs/recipes/dual_gate_lockin_four_terminal_dry_run.yaml",
        tmp_path / "suite",
        measurement_prefix="bad_field",
        magnetic_field_t=1.0,
    )
    minus_data = yaml.safe_load(result.minus_hall_recipe.read_text(encoding="utf-8"))
    minus_data["topology"]["magnetic_field_t"] = -2.0
    result.minus_hall_recipe.write_text(yaml.safe_dump(minus_data, sort_keys=False), encoding="utf-8")

    audit = audit_dual_gate_lockin_hall_suite(
        result.longitudinal_recipe,
        result.plus_hall_recipe,
        result.minus_hall_recipe,
        zero_hall_recipe=result.zero_hall_recipe,
    )

    assert audit.compatible is False
    assert any(issue.check == "magnetic_field_t" for issue in audit.issues)

    code = main(
        [
            "dual-gate-lockin-hall-suite-plan",
            str(result.longitudinal_recipe),
            str(result.plus_hall_recipe),
            str(result.minus_hall_recipe),
            "--zero-field-recipe",
            str(result.zero_hall_recipe),
        ]
    )
    assert code == 2

    code = main(
        [
            "dual-gate-lockin-hall-suite-chunk-plan",
            str(result.longitudinal_recipe),
            str(result.plus_hall_recipe),
            str(result.minus_hall_recipe),
            "--zero-field-recipe",
            str(result.zero_hall_recipe),
            "--chunk-size",
            "2",
        ]
    )
    assert code == 2


def test_cli_dual_gate_lockin_hall_suite_adjust_recipes_updates_group_consistently(tmp_path):
    result = write_dual_gate_lockin_hall_suite_template(
        "configs/recipes/dual_gate_lockin_four_terminal_dry_run.yaml",
        tmp_path / "suite",
        measurement_prefix="feedback_graphene",
        magnetic_field_t=1.0,
    )
    output = tmp_path / "adjusted_suite"

    code = main(
        [
            "dual-gate-lockin-hall-suite-adjust-recipes",
            str(result.longitudinal_recipe),
            str(result.plus_hall_recipe),
            str(result.minus_hall_recipe),
            str(output),
            "--zero-field-recipe",
            str(result.zero_hall_recipe),
            "--measurement-prefix",
            "feedback_graphene_after_chunk1",
            "--gate-nplc",
            "3",
            "--gate-settle-s",
            "0.4",
            "--lockin-sensitivity-index",
            "20",
            "--lockin-time-constant-index",
            "11",
            "--lockin-read-settle-s",
            "0.8",
            "--adjustment-note",
            "chunk feedback: reduce noise before full Hall suite",
        ]
    )

    assert code == 0
    longitudinal_path = output / "feedback_graphene_after_chunk1_vxx.yaml"
    plus_path = output / "feedback_graphene_after_chunk1_vxy_plus_b.yaml"
    minus_path = output / "feedback_graphene_after_chunk1_vxy_minus_b.yaml"
    zero_path = output / "feedback_graphene_after_chunk1_vxy_zero_b.yaml"
    assert longitudinal_path.exists()
    assert plus_path.exists()
    assert minus_path.exists()
    assert zero_path.exists()

    longitudinal = load_dual_gate_lockin_recipe(longitudinal_path)
    plus = load_dual_gate_lockin_recipe(plus_path)
    minus = load_dual_gate_lockin_recipe(minus_path)
    zero = load_dual_gate_lockin_recipe(zero_path)
    for recipe in [longitudinal, plus, minus, zero]:
        assert recipe.gate1_instrument.nplc == 3.0
        assert recipe.gate2_instrument.nplc == 3.0
        assert recipe.gate1_sweep.settle_s == 0.4
        assert recipe.gate2_sweep.settle_s == 0.4
        assert recipe.lockin.sensitivity_index == 20
        assert recipe.lockin.time_constant_index == 11
        assert recipe.lockin.read_settle_s == 0.8
        assert "chunk feedback" in recipe.experiment.notes
    assert longitudinal.topology.voltage_probe_role == "longitudinal"
    assert plus.topology.magnetic_field_t == 1.0
    assert minus.topology.magnetic_field_t == -1.0
    assert zero.topology.magnetic_field_t == 0.0

    audit = audit_dual_gate_lockin_hall_suite(
        longitudinal_path,
        plus_path,
        minus_path,
        zero_hall_recipe=zero_path,
    )
    assert audit.compatible is True
    review = (output / "feedback_graphene_after_chunk1_adjustment_review.md").read_text(encoding="utf-8")
    assert "Dual-Gate Lock-In Hall Suite Adjustment Review" in review
    assert "dual-gate-lockin-hall-suite-check" in review
    assert "dual-gate-lockin-hall-suite-chunk-plan" in review
    assert "Gate1 NPLC" in review


def test_cli_dual_gate_lockin_hall_suite_adjust_recipes_rejects_incompatible_suite(tmp_path):
    result = write_dual_gate_lockin_hall_suite_template(
        "configs/recipes/dual_gate_lockin_four_terminal_dry_run.yaml",
        tmp_path / "suite",
        measurement_prefix="bad_adjust",
        magnetic_field_t=1.0,
    )
    plus_data = yaml.safe_load(result.plus_hall_recipe.read_text(encoding="utf-8"))
    plus_data["gate1_sweep"]["points"] = 4
    result.plus_hall_recipe.write_text(yaml.safe_dump(plus_data, sort_keys=False), encoding="utf-8")

    code = main(
        [
            "dual-gate-lockin-hall-suite-adjust-recipes",
            str(result.longitudinal_recipe),
            str(result.plus_hall_recipe),
            str(result.minus_hall_recipe),
            str(tmp_path / "adjusted_suite"),
            "--zero-field-recipe",
            str(result.zero_hall_recipe),
            "--gate-nplc",
            "2",
        ]
    )

    assert code == 2


def test_cli_dual_gate_lockin_hall_suite_package_writes_portable_runbook_and_zip(tmp_path):
    result = write_dual_gate_lockin_hall_suite_template(
        "configs/recipes/dual_gate_lockin_four_terminal_dry_run.yaml",
        tmp_path / "suite",
        measurement_prefix="package_graphene",
        magnetic_field_t=1.0,
    )
    feedback = tmp_path / "chunk_feedback.md"
    feedback.write_text("Dual-gate lock-in chunk feedback: PASS\n", encoding="utf-8")
    preflight = tmp_path / "preflight.txt"
    preflight.write_text("Dual-gate lock-in preflight OK: True\n", encoding="utf-8")
    output = tmp_path / "packages"

    code = main(
        [
            "dual-gate-lockin-hall-suite-package",
            str(result.longitudinal_recipe),
            str(result.plus_hall_recipe),
            str(result.minus_hall_recipe),
            str(output),
            "--zero-field-recipe",
            str(result.zero_hall_recipe),
            "--package-name",
            "package_graphene_lab1",
            "--chunk-size",
            "4",
            "--max-hardware-points",
            "4",
            "--chunk-feedback-file",
            str(feedback),
            "--preflight-file",
            str(preflight),
            "--acquisition-note",
            "lab laptop handoff package",
        ]
    )

    assert code == 0
    package_dir = output / "package_graphene_lab1"
    runbook = package_dir / "acquisition_runbook.md"
    manifest_path = package_dir / "package_manifest.json"
    zip_path = output / "package_graphene_lab1.zip"
    assert (package_dir / "recipes" / result.longitudinal_recipe.name).exists()
    assert (package_dir / "recipes" / result.plus_hall_recipe.name).exists()
    assert (package_dir / "chunk_feedback" / "chunk_feedback.md").exists()
    assert (package_dir / "preflight" / "preflight.txt").exists()
    assert (package_dir / "keithley_audit" / "longitudinal_keithley_audit.json").exists()
    assert (package_dir / "keithley_audit" / "longitudinal_keithley_audit.md").exists()
    assert (package_dir / "lockin_audit" / "longitudinal_sr860_audit.json").exists()
    assert (package_dir / "lockin_audit" / "longitudinal_sr860_audit.md").exists()
    assert runbook.exists()
    assert manifest_path.exists()
    assert zip_path.exists()

    runbook_text = runbook.read_text(encoding="utf-8")
    assert "Dual-Gate Lock-In Hall Suite Acquisition Package" in runbook_text
    assert "dual-gate-lockin-hall-suite-check" in runbook_text
    assert "dual-gate-lockin-hall-suite-chunk-plan" in runbook_text
    assert "dual-gate-lockin-chunk-feedback" in runbook_text
    assert "dual-gate-lockin-hall-suite-adjust-recipes" in runbook_text
    assert "Keithley Parameter Audits" in runbook_text
    assert "longitudinal_keithley_audit.json" in runbook_text
    assert "SR860 Setting Audits" in runbook_text
    assert "longitudinal_sr860_audit.json" in runbook_text
    assert "lab laptop handoff package" in runbook_text

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["compatible"] is True
    assert manifest["chunk_size"] == 4
    assert manifest["max_hardware_points"] == 4
    assert manifest["point_count"] == 25
    assert manifest["copied_recipes"]["longitudinal"].endswith(result.longitudinal_recipe.name)
    assert manifest["keithley_parameter_audits"]["longitudinal"]["ok_for_hardware"] is True
    assert manifest["keithley_parameter_audits"]["longitudinal"]["json"] == "keithley_audit/longitudinal_keithley_audit.json"
    assert manifest["lockin_setting_audits"]["longitudinal"]["ok_for_hardware"] is True
    assert manifest["lockin_setting_audits"]["longitudinal"]["json"] == "lockin_audit/longitudinal_sr860_audit.json"
    assert manifest["manifest_schema_version"] == 2
    normalized = manifest["measurement_condition_audits"]
    assert normalized["schema_version"] == 1
    assert normalized["ok_for_hardware"] is True
    normalized_records = normalized["records"]
    assert len(normalized_records) == 8
    assert {
        (record["recipe_key"], record["instrument"], record["audit_type"])
        for record in normalized_records
    } >= {
        ("longitudinal", "keithley_2450", "smu_hardware_parameters"),
        ("longitudinal", "srs_sr860", "lockin_expected_settings"),
    }
    assert {record["kind"] for record in manifest["extras"]} == {"chunk_feedback", "preflight"}
    with zipfile.ZipFile(zip_path) as archive:
        names = set(archive.namelist())
    assert "acquisition_runbook.md" in names
    assert "package_manifest.json" in names
    assert f"recipes/{result.longitudinal_recipe.name}" in names
    assert "keithley_audit/longitudinal_keithley_audit.json" in names
    assert "lockin_audit/longitudinal_sr860_audit.json" in names
    validation_json = tmp_path / "package_validation.json"
    validation_code = main(
        [
            "dual-gate-lockin-hall-suite-validate-package",
            str(package_dir),
            "--json-output",
            str(validation_json),
        ]
    )
    validation = json.loads(validation_json.read_text(encoding="utf-8"))
    assert validation_code == 0
    assert validation["valid"] is True
    assert validation["manifest_schema_version"] == 2
    assert validation["recipe_count"] == 4
    smoke_code = main(
        [
            "dual-gate-lockin-hall-suite-lab-smoke-bundle",
            str(package_dir),
        ]
    )
    smoke_dir = package_dir / "lab_smoke"
    smoke_payload = json.loads((smoke_dir / "lab_smoke_bundle.json").read_text(encoding="utf-8"))
    assert smoke_code == 0
    assert (smoke_dir / "lab_smoke_checklist.md").exists()
    assert (smoke_dir / "package_validation.json").exists()
    assert smoke_payload["instrument_count"] == 3
    assert len(smoke_payload["commands"]["preflight"]) == 4
    command_review_json = tmp_path / "hardware_command_review.json"
    command_review_code = main(
        [
            "dual-gate-lockin-hall-suite-hardware-command-review",
            str(package_dir),
            "--json-output",
            str(command_review_json),
        ]
    )
    command_review = json.loads(command_review_json.read_text(encoding="utf-8"))
    assert command_review_code == 0
    assert command_review["valid"] is True
    assert command_review["command_count"] == 4
    handoff_code = main(
        [
            "dual-gate-lockin-hall-suite-handoff-summary",
            str(package_dir),
            "--overwrite",
        ]
    )
    handoff_dir = package_dir / "handoff_summary"
    handoff = json.loads((handoff_dir / "handoff_summary.json").read_text(encoding="utf-8"))
    assert handoff_code == 0
    assert handoff["pass"] is True
    assert (handoff_dir / "handoff_summary.md").exists()
    assert (handoff_dir / "package_validation.json").exists()
    assert (handoff_dir / "hardware_command_review.json").exists()
    lifecycle_json = tmp_path / "lifecycle_status.json"
    lifecycle_code = main(
        [
            "dual-gate-lockin-hall-suite-lifecycle-status",
            str(package_dir),
            "--json-output",
            str(lifecycle_json),
        ]
    )
    lifecycle = json.loads(lifecycle_json.read_text(encoding="utf-8"))
    assert lifecycle_code == 0
    assert lifecycle["state"] == "ready_for_lab_handoff"
    assert lifecycle["measurement_conditions_ready"] is True
    assert lifecycle["ready_for_lab_handoff"] is True
    lifecycle_stage_by_key = {stage["key"]: stage for stage in lifecycle["stages"]}
    assert lifecycle_stage_by_key["measurement_condition_audits"]["ok"] is True
    assert lifecycle_stage_by_key["keithley_parameter_audits"]["ok"] is True
    assert lifecycle_stage_by_key["lockin_setting_audits"]["ok"] is True


def test_cli_dual_gate_lockin_hall_suite_package_rejects_invalid_chunk_size(tmp_path):
    result = write_dual_gate_lockin_hall_suite_template(
        "configs/recipes/dual_gate_lockin_four_terminal_dry_run.yaml",
        tmp_path / "suite",
        measurement_prefix="bad_package",
        magnetic_field_t=1.0,
    )

    code = main(
        [
            "dual-gate-lockin-hall-suite-package",
            str(result.longitudinal_recipe),
            str(result.plus_hall_recipe),
            str(result.minus_hall_recipe),
            str(tmp_path / "packages"),
            "--zero-field-recipe",
            str(result.zero_hall_recipe),
            "--chunk-size",
            "0",
        ]
    )

    assert code == 2


def test_cli_dual_gate_lockin_hall_suite_intake_accepts_packaged_completed_runs(tmp_path):
    result = write_dual_gate_lockin_hall_suite_template(
        "configs/recipes/dual_gate_lockin_four_terminal_dry_run.yaml",
        tmp_path / "suite",
        measurement_prefix="intake_graphene",
        magnetic_field_t=1.0,
        run_output_directory=tmp_path / "raw",
    )
    shrink_hall_suite_for_intake_tests(result)
    package_code = main(
        [
            "dual-gate-lockin-hall-suite-package",
            str(result.longitudinal_recipe),
            str(result.plus_hall_recipe),
            str(result.minus_hall_recipe),
            str(tmp_path / "packages"),
            "--zero-field-recipe",
            str(result.zero_hall_recipe),
            "--package-name",
            "intake_graphene_package",
            "--chunk-size",
            "5",
        ]
    )
    assert package_code == 0
    package_dir = tmp_path / "packages" / "intake_graphene_package"
    recipe_dir = package_dir / "recipes"
    long_run = run_hall_suite_recipe_dry(recipe_dir / result.longitudinal_recipe.name)
    plus_run = run_hall_suite_recipe_dry(recipe_dir / result.plus_hall_recipe.name)
    minus_run = run_hall_suite_recipe_dry(recipe_dir / result.minus_hall_recipe.name)
    zero_run = run_hall_suite_recipe_dry(recipe_dir / result.zero_hall_recipe.name)

    code = main(
        [
            "dual-gate-lockin-hall-suite-intake",
            str(package_dir),
            str(long_run),
            str(plus_run),
            str(minus_run),
            "--zero-field-run-dir",
            str(zero_run),
            "--allow-missing-lockin-settings",
        ]
    )

    assert code == 0
    report = package_dir / "result_intake_report.md"
    payload = json.loads((package_dir / "result_intake.json").read_text(encoding="utf-8"))
    assert report.exists()
    assert "Accepted for Hall analysis: True" in report.read_text(encoding="utf-8")
    assert payload["accepted"] is True
    assert payload["runs"]["longitudinal"]["points_written"] == 4
    snapshot_json = tmp_path / "condition_snapshot.json"
    snapshot_md = tmp_path / "condition_snapshot.md"
    snapshot_code = main(
        [
            "dual-gate-lockin-hall-suite-condition-snapshot",
            str(package_dir),
            "--json-output",
            str(snapshot_json),
            "--output",
            str(snapshot_md),
        ]
    )
    snapshot = json.loads(snapshot_json.read_text(encoding="utf-8"))
    snapshot_text = snapshot_md.read_text(encoding="utf-8")
    assert snapshot_code == 0
    assert [run["run_key"] for run in snapshot["runs"]] == ["longitudinal", "plus", "minus", "zero"]
    assert snapshot["runs"][0]["gate1"]["nplc"] == 1.0
    assert snapshot["runs"][0]["gate2"]["current_compliance_a"] == 1e-8
    assert snapshot["runs"][0]["lockin"]["time_constant_index"] == 10
    assert "Hall Suite Run Condition Snapshot" in snapshot_text
    assert "| longitudinal | gate1 |" in snapshot_text
    assert "| plus |" in snapshot_text
    drift_json = tmp_path / "condition_drift.json"
    drift_code = main(
        [
            "dual-gate-lockin-hall-suite-condition-drift",
            str(package_dir),
            "--json-output",
            str(drift_json),
            "--output",
            str(tmp_path / "condition_drift.md"),
        ]
    )
    drift = json.loads(drift_json.read_text(encoding="utf-8"))
    assert drift_code == 0
    assert drift["accepted"] is True
    assert drift["issues"] == []

    plus_metadata_path = Path(plus_run) / "metadata.json"
    plus_metadata = json.loads(plus_metadata_path.read_text(encoding="utf-8"))
    original_nplc = plus_metadata["recipe"]["gate1_instrument"]["nplc"]
    plus_metadata["recipe"]["gate1_instrument"]["nplc"] = 3.0
    plus_metadata_path.write_text(json.dumps(plus_metadata, indent=2, sort_keys=True), encoding="utf-8")
    drift_fail_json = tmp_path / "condition_drift_fail.json"
    drift_fail_code = main(
        [
            "dual-gate-lockin-hall-suite-condition-drift",
            str(package_dir),
            "--json-output",
            str(drift_fail_json),
            "--output",
            str(tmp_path / "condition_drift_fail.md"),
        ]
    )
    drift_fail = json.loads(drift_fail_json.read_text(encoding="utf-8"))
    assert drift_fail_code == 2
    assert drift_fail["accepted"] is False
    assert any(issue["field"] == "gate1_instrument.nplc" for issue in drift_fail["issues"])
    analyze_drift_code = main(["dual-gate-lockin-hall-suite-analyze", str(package_dir)])
    assert analyze_drift_code == 2
    plus_metadata["recipe"]["gate1_instrument"]["nplc"] = original_nplc
    plus_metadata_path.write_text(json.dumps(plus_metadata, indent=2, sort_keys=True), encoding="utf-8")
    default_snapshot_code = main(["dual-gate-lockin-hall-suite-condition-snapshot", str(package_dir)])
    assert default_snapshot_code == 0
    default_drift_code = main(["dual-gate-lockin-hall-suite-condition-drift", str(package_dir)])
    assert default_drift_code == 0

    return_code = main(
        [
            "dual-gate-lockin-hall-suite-lab-return-manifest",
            str(package_dir),
            "--operator-note",
            "returned from lab laptop",
            "--overwrite",
        ]
    )
    assert return_code == 0
    return_manifest = json.loads((package_dir / "lab_return" / "lab_return_manifest.json").read_text(encoding="utf-8"))
    assert return_manifest["ready_for_analysis"] is True
    assert return_manifest["operator_note"] == "returned from lab laptop"
    assert return_manifest["condition_snapshot_written"] is True
    assert return_manifest["condition_drift_accepted"] is True
    assert set(return_manifest["runs"]) == {"longitudinal", "plus", "minus", "zero"}
    lifecycle_json = tmp_path / "returned_lifecycle_status.json"
    lifecycle_code = main(
        [
            "dual-gate-lockin-hall-suite-lifecycle-status",
            str(package_dir),
            "--json-output",
            str(lifecycle_json),
        ]
    )
    lifecycle = json.loads(lifecycle_json.read_text(encoding="utf-8"))
    assert lifecycle_code == 0
    assert lifecycle["state"] == "ready_for_analysis"
    assert lifecycle["measurement_conditions_ready"] is True
    assert lifecycle["ready_for_analysis"] is True
    lifecycle_stage_by_key = {stage["key"]: stage for stage in lifecycle["stages"]}
    assert lifecycle_stage_by_key["condition_snapshot"]["ok"] is True
    assert lifecycle_stage_by_key["condition_drift"]["ok"] is True

    code = main(
        [
            "dual-gate-lockin-hall-suite-analyze",
            str(package_dir),
        ]
    )
    assert code == 0
    analysis_dir = package_dir / "hall_analysis"
    manifest = json.loads((analysis_dir / "hall_suite_analysis_manifest.json").read_text(encoding="utf-8"))
    assert (analysis_dir / "antisym" / "hall_antisym.csv").exists()
    assert (analysis_dir / "zero_corrected" / "hall_zero_corrected.csv").exists()
    assert (analysis_dir / "mobility" / "hall_mobility.csv").exists()
    assert (analysis_dir / "hall_suite_analysis_report.md").exists()
    assert manifest["outputs"]["zero_corrected_csv"].endswith("hall_zero_corrected.csv")
    assert manifest["hall_density_source"].endswith("hall_zero_corrected.csv")

    code = main(["dual-gate-lockin-hall-suite-review", str(analysis_dir)])
    assert code == 0
    review_json = analysis_dir / "hall_suite_analysis_review.json"
    review_payload = json.loads(review_json.read_text(encoding="utf-8"))
    review_text = (analysis_dir / "hall_suite_analysis_review.md").read_text(encoding="utf-8")
    assert review_payload["accepted_for_next_scan_decision"] is True
    assert review_payload["summary"]["mobility"]["gate_points"] == 4
    assert "mobility_magnitude_cm2_per_v_s" in review_text

    mobility_csv = analysis_dir / "mobility" / "hall_mobility.csv"
    with mobility_csv.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])
    rows[0]["hall_carrier_density_per_m2"] = "1.0e12"
    rows[1]["hall_carrier_density_per_m2"] = "-1.0e12"
    with mobility_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames))
        writer.writeheader()
        writer.writerows(rows)
    code = main(["dual-gate-lockin-hall-suite-review", str(analysis_dir), "--overwrite"])
    assert code == 0
    review_payload = json.loads(review_json.read_text(encoding="utf-8"))
    assert any(issue["check"] == "mobility_density.sign_change" for issue in review_payload["issues"])

    code = main(["dual-gate-lockin-hall-suite-next-scan-proposal", str(analysis_dir)])
    assert code == 0
    proposal_json = analysis_dir / "hall_suite_next_scan_proposal.json"
    proposal_payload = json.loads(proposal_json.read_text(encoding="utf-8"))
    proposal_text = (analysis_dir / "hall_suite_next_scan_proposal.md").read_text(encoding="utf-8")
    assert proposal_payload["hardware_recipe_written"] is False
    assert proposal_payload["accepted_for_recipe_generation"] is False
    assert proposal_payload["requires_lab_approval"] is True
    assert proposal_payload["strategy"] == "refine_charge_neutrality_region"
    assert "NPLC" in proposal_text

    code = main(
        [
            "dual-gate-lockin-hall-suite-approved-next-scan",
            str(analysis_dir),
            str(tmp_path / "approved_suite"),
            "--approval-note",
            "approved in lab notebook NB-001 after reviewing sign change",
            "--measurement-prefix",
            "approved_graphene",
        ]
    )
    assert code == 0
    approved_recipe = load_dual_gate_lockin_recipe(tmp_path / "approved_suite" / "approved_graphene_vxx.yaml")
    proposed_gate1 = proposal_payload["proposed_gate_grid"]["gate1"]
    proposed_gate2 = proposal_payload["proposed_gate_grid"]["gate2"]
    assert approved_recipe.gate1_sweep.start_v == proposed_gate1["start_v"]
    assert approved_recipe.gate1_sweep.stop_v == proposed_gate1["stop_v"]
    assert approved_recipe.gate1_sweep.points == proposed_gate1["points"]
    assert approved_recipe.gate2_sweep.start_v == proposed_gate2["start_v"]
    assert approved_recipe.gate1_instrument.nplc == 1.0
    assert (tmp_path / "approved_suite" / "approved_graphene_approved_next_scan_review.md").exists()

    code = main(
        [
            "dual-gate-lockin-hall-suite-approved-next-scan-package",
            str(tmp_path / "approved_suite" / "approved_graphene_vxx.yaml"),
            str(tmp_path / "approved_suite" / "approved_graphene_vxy_plus_b.yaml"),
            str(tmp_path / "approved_suite" / "approved_graphene_vxy_minus_b.yaml"),
            str(tmp_path / "approved_packages"),
            "--zero-field-recipe",
            str(tmp_path / "approved_suite" / "approved_graphene_vxy_zero_b.yaml"),
            "--proposal-json",
            str(proposal_json),
            "--approval-review",
            str(tmp_path / "approved_suite" / "approved_graphene_approved_next_scan_review.md"),
            "--package-name",
            "approved_graphene_package",
            "--chunk-size",
            "5",
        ]
    )
    assert code == 0
    approved_package = tmp_path / "approved_packages" / "approved_graphene_package"
    approved_manifest = json.loads((approved_package / "package_manifest.json").read_text(encoding="utf-8"))
    approved_runbook = (approved_package / "acquisition_runbook.md").read_text(encoding="utf-8")
    names = zipfile.ZipFile(approved_package.with_suffix(".zip")).namelist()
    assert approved_manifest["approved_next_scan"]["strategy"] == "refine_charge_neutrality_region"
    assert "Approved Next-Scan Provenance" in approved_runbook
    assert any(name.endswith("hall_suite_next_scan_proposal.json") for name in names)
    assert any(name.endswith("approved_graphene_approved_next_scan_review.md") for name in names)

    code = main(
        [
            "dual-gate-lockin-hall-suite-approved-next-scan-rehearse",
            str(approved_package),
        ]
    )
    assert code == 0
    rehearsal = approved_package / "dry_run_rehearsal"
    rehearsal_payload = json.loads((rehearsal / "rehearsal_summary.json").read_text(encoding="utf-8"))
    assert rehearsal_payload["completed"] is True
    assert "approved_next_scan" in rehearsal_payload
    assert (rehearsal / "hall_analysis" / "hall_suite_analysis_review.json").exists()
    assert (rehearsal / "hall_analysis" / "hall_suite_next_scan_proposal.json").exists()

    status_json = tmp_path / "approved_status.json"
    code = main(
        [
            "dual-gate-lockin-hall-suite-status",
            str(approved_package),
            "--json-output",
            str(status_json),
        ]
    )
    assert code == 0
    status_payload = json.loads(status_json.read_text(encoding="utf-8"))
    assert status_payload["ready_for_lab_review"] is True
    stage_by_key = {stage["key"]: stage for stage in status_payload["stages"]}
    assert stage_by_key["approved_next_scan"]["ok"] is True
    assert stage_by_key["dry_run_rehearsal"]["ok"] is True
    assert stage_by_key["recipes"]["details"] == "4 recipes"


def test_cli_dual_gate_lockin_hall_suite_intake_rejects_recipe_mismatch(tmp_path):
    result = write_dual_gate_lockin_hall_suite_template(
        "configs/recipes/dual_gate_lockin_four_terminal_dry_run.yaml",
        tmp_path / "suite",
        measurement_prefix="bad_intake_graphene",
        magnetic_field_t=1.0,
        run_output_directory=tmp_path / "raw",
    )
    shrink_hall_suite_for_intake_tests(result)
    code = main(
        [
            "dual-gate-lockin-hall-suite-package",
            str(result.longitudinal_recipe),
            str(result.plus_hall_recipe),
            str(result.minus_hall_recipe),
            str(tmp_path / "packages"),
            "--zero-field-recipe",
            str(result.zero_hall_recipe),
            "--package-name",
            "bad_intake_package",
            "--chunk-size",
            "5",
        ]
    )
    assert code == 0
    package_dir = tmp_path / "packages" / "bad_intake_package"
    recipe_dir = package_dir / "recipes"
    long_run = run_hall_suite_recipe_dry(recipe_dir / result.longitudinal_recipe.name)
    plus_run = run_hall_suite_recipe_dry(recipe_dir / result.plus_hall_recipe.name)
    zero_run = run_hall_suite_recipe_dry(recipe_dir / result.zero_hall_recipe.name)

    code = main(
        [
            "dual-gate-lockin-hall-suite-intake",
            str(package_dir),
            str(long_run),
            str(plus_run),
            str(long_run),
            "--zero-field-run-dir",
            str(zero_run),
            "--allow-missing-lockin-settings",
        ]
    )

    assert code == 2
    payload = json.loads((package_dir / "result_intake.json").read_text(encoding="utf-8"))
    assert payload["accepted"] is False
    assert any(issue["check"] == "minus.recipe_match" for issue in payload["issues"])

    code = main(["dual-gate-lockin-hall-suite-analyze", str(package_dir)])
    assert code == 2
    assert not (package_dir / "hall_analysis").exists()


def test_cli_dual_gate_lockin_hall_suite_review_rejects_missing_analysis_artifacts(tmp_path):
    analysis_dir = tmp_path / "missing_analysis"
    analysis_dir.mkdir()

    code = main(["dual-gate-lockin-hall-suite-review", str(analysis_dir)])

    assert code == 2
    payload = json.loads((analysis_dir / "hall_suite_analysis_review.json").read_text(encoding="utf-8"))
    assert payload["accepted_for_next_scan_decision"] is False
    assert any(issue["severity"] == "error" for issue in payload["issues"])

    code = main(["dual-gate-lockin-hall-suite-next-scan-proposal", str(analysis_dir)])
    assert code == 2
    assert not (analysis_dir / "hall_suite_next_scan_proposal.json").exists()

    code = main(
        [
            "dual-gate-lockin-hall-suite-approved-next-scan",
            str(analysis_dir),
            str(tmp_path / "blocked_approved_suite"),
            "--approval-note",
            "should fail because proposal is missing",
        ]
    )
    assert code == 2
