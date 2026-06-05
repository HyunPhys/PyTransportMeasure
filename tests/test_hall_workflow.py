import json

import yaml

from pytransport.dual_gate_lockin_hall_suite import (
    write_dual_gate_lockin_hall_suite_acquisition_package,
    write_dual_gate_lockin_hall_suite_template,
)
from pytransport.hall_workflow import (
    format_dual_gate_lockin_hall_suite_lifecycle_status,
    format_dual_gate_lockin_hall_suite_package_validation,
    format_dual_gate_lockin_hall_suite_workflow_status,
    inspect_dual_gate_lockin_hall_suite_lifecycle_status,
    inspect_dual_gate_lockin_hall_suite_workflow_status,
    review_dual_gate_lockin_hall_suite_hardware_commands,
    run_dual_gate_lockin_hall_suite_approved_next_scan_rehearsal,
    validate_dual_gate_lockin_hall_suite_package_manifest,
    write_dual_gate_lockin_hall_suite_handoff_summary,
    write_dual_gate_lockin_hall_suite_lab_return_manifest,
    write_dual_gate_lockin_hall_suite_lab_smoke_bundle,
)


def test_hall_workflow_status_reports_package_stage_readiness(tmp_path):
    package_dir = tmp_path / "package"
    recipes_dir = package_dir / "recipes"
    recipes_dir.mkdir(parents=True)
    recipe_paths = {}
    for key in ["longitudinal", "plus", "minus", "zero"]:
        recipe = recipes_dir / f"{key}.yaml"
        recipe.write_text("measurement_name: fake\n", encoding="utf-8")
        recipe_paths[key] = f"recipes/{recipe.name}"
    audit_dir = package_dir / "keithley_audit"
    audit_dir.mkdir()
    keithley_audits = {}
    for key in ["longitudinal", "plus", "minus", "zero"]:
        json_path = audit_dir / f"{key}_keithley_audit.json"
        markdown_path = audit_dir / f"{key}_keithley_audit.md"
        json_path.write_text(json.dumps({"ok_for_hardware": True}), encoding="utf-8")
        markdown_path.write_text("# audit\n", encoding="utf-8")
        keithley_audits[key] = {
            "json": f"keithley_audit/{json_path.name}",
            "markdown": f"keithley_audit/{markdown_path.name}",
            "ok_for_hardware": True,
        }
    lockin_audit_dir = package_dir / "lockin_audit"
    lockin_audit_dir.mkdir()
    lockin_audits = {}
    for key in ["longitudinal", "plus", "minus", "zero"]:
        json_path = lockin_audit_dir / f"{key}_sr860_audit.json"
        markdown_path = lockin_audit_dir / f"{key}_sr860_audit.md"
        json_path.write_text(json.dumps({"ok_for_hardware": True}), encoding="utf-8")
        markdown_path.write_text("# audit\n", encoding="utf-8")
        lockin_audits[key] = {
            "json": f"lockin_audit/{json_path.name}",
            "markdown": f"lockin_audit/{markdown_path.name}",
            "ok_for_hardware": True,
        }
    (package_dir / "acquisition_runbook.md").write_text("# runbook\n", encoding="utf-8")
    package_dir.with_suffix(".zip").write_bytes(b"fake zip placeholder")
    normalized_records = []
    for key, record in keithley_audits.items():
        normalized_records.append(
            {
                "recipe_key": key,
                "instrument": "keithley_2450",
                "audit_type": "smu_hardware_parameters",
                **record,
            }
        )
    for key, record in lockin_audits.items():
        normalized_records.append(
            {
                "recipe_key": key,
                "instrument": "srs_sr860",
                "audit_type": "lockin_expected_settings",
                **record,
            }
        )
    manifest = {
        "package_name": "fake_package",
        "copied_recipes": recipe_paths,
        "keithley_parameter_audits": keithley_audits,
        "lockin_setting_audits": lockin_audits,
        "measurement_condition_audits": {
            "schema_version": 1,
            "ok_for_hardware": True,
            "records": normalized_records,
        },
        "approved_next_scan": {"strategy": "refine_charge_neutrality_region"},
    }
    (package_dir / "package_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    payload = inspect_dual_gate_lockin_hall_suite_workflow_status(package_dir)
    text = format_dual_gate_lockin_hall_suite_workflow_status(payload)

    assert payload["ready_for_lab_review"] is True
    stage_by_key = {stage["key"]: stage for stage in payload["stages"]}
    assert stage_by_key["recipes"]["ok"] is True
    assert stage_by_key["recipes"]["details"] == "4 recipes"
    assert stage_by_key["keithley_parameter_audits"]["ok"] is True
    assert stage_by_key["keithley_parameter_audits"]["details"] == "4 recipe audits"
    assert stage_by_key["lockin_setting_audits"]["ok"] is True
    assert stage_by_key["lockin_setting_audits"]["details"] == "4 recipe audits"
    assert stage_by_key["dry_run_rehearsal"]["ok"] is False
    assert "Ready for lab review: True" in text
    assert "| Keithley parameter audits | PASS |" in text
    assert "| SR860 setting audits | PASS |" in text
    assert "| Dry-run rehearsal | MISSING |" in text


def test_hall_workflow_status_supports_legacy_audit_manifest(tmp_path):
    package_dir = tmp_path / "legacy_package"
    (package_dir / "recipes").mkdir(parents=True)
    (package_dir / "keithley_audit").mkdir()
    (package_dir / "lockin_audit").mkdir()
    for key in ["longitudinal", "plus", "minus"]:
        (package_dir / "recipes" / f"{key}.yaml").write_text("measurement_name: fake\n", encoding="utf-8")
        (package_dir / "keithley_audit" / f"{key}.json").write_text("{}", encoding="utf-8")
        (package_dir / "keithley_audit" / f"{key}.md").write_text("# audit\n", encoding="utf-8")
        (package_dir / "lockin_audit" / f"{key}.json").write_text("{}", encoding="utf-8")
        (package_dir / "lockin_audit" / f"{key}.md").write_text("# audit\n", encoding="utf-8")
    (package_dir / "acquisition_runbook.md").write_text("# runbook\n", encoding="utf-8")
    package_dir.with_suffix(".zip").write_bytes(b"zip")
    manifest = {
        "package_name": "legacy_package",
        "copied_recipes": {key: f"recipes/{key}.yaml" for key in ["longitudinal", "plus", "minus"]},
        "keithley_parameter_audits": {
            key: {
                "json": f"keithley_audit/{key}.json",
                "markdown": f"keithley_audit/{key}.md",
                "ok_for_hardware": True,
            }
            for key in ["longitudinal", "plus", "minus"]
        },
        "lockin_setting_audits": {
            key: {
                "json": f"lockin_audit/{key}.json",
                "markdown": f"lockin_audit/{key}.md",
                "ok_for_hardware": True,
            }
            for key in ["longitudinal", "plus", "minus"]
        },
    }
    (package_dir / "package_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    payload = inspect_dual_gate_lockin_hall_suite_workflow_status(package_dir)
    stage_by_key = {stage["key"]: stage for stage in payload["stages"]}

    assert payload["ready_for_lab_review"] is True
    assert stage_by_key["keithley_parameter_audits"]["ok"] is True
    assert stage_by_key["lockin_setting_audits"]["ok"] is True


def test_hall_workflow_status_requires_package_manifest(tmp_path):
    missing_package = tmp_path / "missing_package"
    missing_package.mkdir()

    try:
        inspect_dual_gate_lockin_hall_suite_workflow_status(missing_package)
    except FileNotFoundError as exc:
        assert "Package manifest does not exist" in str(exc)
    else:
        raise AssertionError("Expected FileNotFoundError")


def test_hall_package_validator_accepts_generated_package(tmp_path):
    package = _write_small_hall_package(tmp_path)

    payload = validate_dual_gate_lockin_hall_suite_package_manifest(package.package_dir)
    text = format_dual_gate_lockin_hall_suite_package_validation(payload)

    assert payload["valid"] is True
    assert payload["manifest_schema_version"] == 2
    assert payload["recipe_count"] == 4
    assert payload["issues"] == []
    assert "Valid for lab handoff: True" in text
    assert "| Measurement-condition audit records | PASS |" in text


def test_hall_package_records_four_terminal_ac_smoke_prerequisite(tmp_path):
    intake_json = _write_four_terminal_ac_smoke_intake_json(tmp_path)
    template = write_dual_gate_lockin_hall_suite_template(
        "configs/recipes/dual_gate_lockin_four_terminal_dry_run.yaml",
        tmp_path / "suite",
        measurement_prefix="workflow_graphene_prereq",
        magnetic_field_t=1.0,
        run_output_directory=tmp_path / "raw",
    )
    _shrink_suite_recipes(
        [
            template.longitudinal_recipe,
            template.plus_hall_recipe,
            template.minus_hall_recipe,
            template.zero_hall_recipe,
        ]
    )

    package = write_dual_gate_lockin_hall_suite_acquisition_package(
        template.longitudinal_recipe,
        template.plus_hall_recipe,
        template.minus_hall_recipe,
        tmp_path / "packages",
        zero_hall_recipe=template.zero_hall_recipe,
        package_name="workflow_graphene_prereq_package",
        chunk_size=5,
        four_terminal_ac_smoke_intake_json=intake_json,
    )
    manifest = json.loads(package.manifest_path.read_text(encoding="utf-8"))
    runbook = package.runbook_path.read_text(encoding="utf-8")
    prereq = manifest["prerequisites"]["four_terminal_ac_smoke_intake"]
    validation = validate_dual_gate_lockin_hall_suite_package_manifest(package.package_dir)
    status = inspect_dual_gate_lockin_hall_suite_workflow_status(package.package_dir)
    check_by_key = {check["key"]: check for check in validation["checks"]}
    stage_by_key = {stage["key"]: stage for stage in status["stages"]}

    assert prereq["accepted"] is True
    assert prereq["lockin_voltage_input"] == "a-b"
    assert prereq["source_nplc"] == 1.0
    assert (package.package_dir / prereq["path"]).exists()
    assert "Four-terminal AC smoke intake: PASS" in runbook
    assert "SR860 voltage contacts: Vxx+, Vxx-" in runbook
    assert validation["valid"] is True
    assert check_by_key["four_terminal_ac_smoke_accepted"]["ok"] is True
    assert check_by_key["four_terminal_ac_smoke_contacts"]["ok"] is True
    assert stage_by_key["four_terminal_ac_smoke_prerequisite"]["ok"] is True
    assert "NPLC=1.0" in stage_by_key["four_terminal_ac_smoke_prerequisite"]["details"]


def test_hall_package_rejects_failed_four_terminal_ac_smoke_prerequisite(tmp_path):
    intake_json = _write_four_terminal_ac_smoke_intake_json(tmp_path, accepted=False)
    template = write_dual_gate_lockin_hall_suite_template(
        "configs/recipes/dual_gate_lockin_four_terminal_dry_run.yaml",
        tmp_path / "suite",
        measurement_prefix="workflow_graphene_bad_prereq",
        magnetic_field_t=1.0,
        run_output_directory=tmp_path / "raw",
    )
    _shrink_suite_recipes(
        [
            template.longitudinal_recipe,
            template.plus_hall_recipe,
            template.minus_hall_recipe,
            template.zero_hall_recipe,
        ]
    )

    try:
        write_dual_gate_lockin_hall_suite_acquisition_package(
            template.longitudinal_recipe,
            template.plus_hall_recipe,
            template.minus_hall_recipe,
            tmp_path / "packages",
            zero_hall_recipe=template.zero_hall_recipe,
            package_name="workflow_graphene_bad_prereq_package",
            chunk_size=5,
            four_terminal_ac_smoke_intake_json=intake_json,
        )
    except ValueError as exc:
        assert "four-terminal AC smoke intake prerequisite failed" in str(exc)
        assert "accepted must be true" in str(exc)
    else:
        raise AssertionError("Expected failed prerequisite to block package generation")


def test_hall_package_validator_reports_missing_audit_artifact(tmp_path):
    package = _write_small_hall_package(tmp_path)
    missing = package.package_dir / "keithley_audit" / "longitudinal_keithley_audit.json"
    missing.unlink()

    payload = validate_dual_gate_lockin_hall_suite_package_manifest(package.manifest_path)

    assert payload["valid"] is False
    assert any(issue["code"] == "missing_audit_record_json" for issue in payload["issues"])
    assert any(issue["path"] == str(missing) for issue in payload["issues"])


def test_hall_lab_smoke_bundle_writes_identify_probe_and_preflight_commands(tmp_path):
    package = _write_small_hall_package(tmp_path)

    payload = write_dual_gate_lockin_hall_suite_lab_smoke_bundle(package.package_dir)

    smoke_dir = package.package_dir / "lab_smoke"
    checklist = (smoke_dir / "lab_smoke_checklist.md").read_text(encoding="utf-8")
    saved = json.loads((smoke_dir / "lab_smoke_bundle.json").read_text(encoding="utf-8"))
    assert payload["completed"] is True
    assert payload["instrument_count"] == 3
    assert (smoke_dir / "package_validation.json").exists()
    assert len(saved["commands"]["identify"]) == 3
    assert len(saved["commands"]["probe"]) == 3
    assert len(saved["commands"]["preflight"]) == 4
    assert len(saved["commands"]["post_run_intake"]) == 2
    assert saved["return_contract"]["required_run_roles"] == ["longitudinal", "plus", "minus"]
    assert saved["return_contract"]["optional_run_roles"] == ["zero"]
    assert any("--instrument keithley_2450" in command for command in saved["commands"]["identify"])
    assert any("--instrument srs_sr860" in command for command in saved["commands"]["probe"])
    assert "dual-gate-lockin-hall-suite-intake" in saved["commands"]["post_run_intake"][0]
    assert "--zero-field-run-dir data\\raw\\<zero_B_run>" in saved["commands"]["post_run_intake"][0]
    assert "ptm list-resources" in checklist
    assert "Every dual-gate lock-in preflight reports OK" in checklist
    assert "## 7. Post-Run Intake And Return" in checklist
    assert "result_intake.json" in checklist


def test_hall_lab_smoke_bundle_reports_four_terminal_ac_prerequisite(tmp_path):
    intake_json = _write_four_terminal_ac_smoke_intake_json(tmp_path)
    template = write_dual_gate_lockin_hall_suite_template(
        "configs/recipes/dual_gate_lockin_four_terminal_dry_run.yaml",
        tmp_path / "suite",
        measurement_prefix="workflow_graphene_smoke_prereq",
        magnetic_field_t=1.0,
        run_output_directory=tmp_path / "raw",
    )
    _shrink_suite_recipes(
        [
            template.longitudinal_recipe,
            template.plus_hall_recipe,
            template.minus_hall_recipe,
            template.zero_hall_recipe,
        ]
    )
    package = write_dual_gate_lockin_hall_suite_acquisition_package(
        template.longitudinal_recipe,
        template.plus_hall_recipe,
        template.minus_hall_recipe,
        tmp_path / "packages",
        zero_hall_recipe=template.zero_hall_recipe,
        package_name="workflow_graphene_smoke_prereq_package",
        chunk_size=5,
        four_terminal_ac_smoke_intake_json=intake_json,
    )

    payload = write_dual_gate_lockin_hall_suite_lab_smoke_bundle(package.package_dir)

    smoke_dir = package.package_dir / "lab_smoke"
    checklist = (smoke_dir / "lab_smoke_checklist.md").read_text(encoding="utf-8")
    saved = json.loads((smoke_dir / "lab_smoke_bundle.json").read_text(encoding="utf-8"))
    assert payload["four_terminal_ac_smoke_prerequisite"]["present"] is True
    assert saved["four_terminal_ac_smoke_prerequisite"]["ok"] is True
    assert "## Measurement Prerequisites" in checklist
    assert "Status: PASS" in checklist


def test_hall_hardware_command_review_accepts_guarded_package_runbook(tmp_path):
    package = _write_small_hall_package(tmp_path)

    payload = review_dual_gate_lockin_hall_suite_hardware_commands(package.package_dir)

    assert payload["valid"] is True
    assert payload["command_count"] == 4
    assert payload["expected_chunk_size"] == 5
    assert all(check["ok"] for check in payload["checks"])


def test_hall_hardware_command_review_rejects_missing_approval_note(tmp_path):
    package = _write_small_hall_package(tmp_path)
    runbook = package.package_dir / "acquisition_runbook.md"
    text = runbook.read_text(encoding="utf-8").replace(' --hardware-approval-note "<lab note>"', "", 1)
    runbook.write_text(text, encoding="utf-8")

    payload = review_dual_gate_lockin_hall_suite_hardware_commands(package.package_dir)

    assert payload["valid"] is False
    assert any(issue["code"] == "missing_hardware_approval_note" for issue in payload["issues"])


def test_hall_handoff_summary_writes_single_pass_index(tmp_path):
    package = _write_small_hall_package(tmp_path)

    payload = write_dual_gate_lockin_hall_suite_handoff_summary(package.package_dir)

    summary_dir = package.package_dir / "handoff_summary"
    summary = json.loads((summary_dir / "handoff_summary.json").read_text(encoding="utf-8"))
    report = (summary_dir / "handoff_summary.md").read_text(encoding="utf-8")
    assert payload["pass"] is True
    assert summary["checks"]["hardware_command_review"] is True
    assert summary["checks"]["lab_smoke_bundle"] is True
    assert summary["checks"]["package_validation"] is True
    assert summary["checks"]["four_terminal_ac_smoke_prerequisite"] is True
    assert summary["four_terminal_ac_smoke_prerequisite"]["present"] is False
    assert (summary_dir / "package_validation.json").exists()
    assert (summary_dir / "hardware_command_review.json").exists()
    assert (summary_dir / "lab_smoke_bundle.json").exists()
    assert "Ready for lab handoff: True" in report


def test_hall_handoff_summary_reports_four_terminal_ac_prerequisite(tmp_path):
    intake_json = _write_four_terminal_ac_smoke_intake_json(tmp_path)
    template = write_dual_gate_lockin_hall_suite_template(
        "configs/recipes/dual_gate_lockin_four_terminal_dry_run.yaml",
        tmp_path / "suite",
        measurement_prefix="workflow_graphene_handoff_prereq",
        magnetic_field_t=1.0,
        run_output_directory=tmp_path / "raw",
    )
    _shrink_suite_recipes(
        [
            template.longitudinal_recipe,
            template.plus_hall_recipe,
            template.minus_hall_recipe,
            template.zero_hall_recipe,
        ]
    )
    package = write_dual_gate_lockin_hall_suite_acquisition_package(
        template.longitudinal_recipe,
        template.plus_hall_recipe,
        template.minus_hall_recipe,
        tmp_path / "packages",
        zero_hall_recipe=template.zero_hall_recipe,
        package_name="workflow_graphene_handoff_prereq_package",
        chunk_size=5,
        four_terminal_ac_smoke_intake_json=intake_json,
    )

    payload = write_dual_gate_lockin_hall_suite_handoff_summary(package.package_dir)

    summary = json.loads((package.package_dir / "handoff_summary" / "handoff_summary.json").read_text(encoding="utf-8"))
    report = (package.package_dir / "handoff_summary" / "handoff_summary.md").read_text(encoding="utf-8")
    assert payload["pass"] is True
    assert summary["checks"]["four_terminal_ac_smoke_prerequisite"] is True
    assert summary["four_terminal_ac_smoke_prerequisite"]["present"] is True
    assert summary["four_terminal_ac_smoke_prerequisite"]["ok"] is True
    assert "| Four-terminal AC smoke prerequisite | PASS |" in report
    assert "## Four-Terminal AC Prerequisite" in report
    assert "Status: PASS" in report


def test_hall_lab_return_manifest_records_accepted_intake(tmp_path):
    package = _write_small_hall_package(tmp_path)
    intake = {
        "package_manifest_path": str(package.manifest_path),
        "accepted": True,
        "issues": [],
        "runs": {
            "longitudinal": {
                "run_dir": str(tmp_path / "raw" / "vxx"),
                "accepted": True,
                "completed": True,
                "points_written": 4,
                "planned_points": 4,
                "remaining_points": 0,
            },
            "plus": {
                "run_dir": str(tmp_path / "raw" / "plus"),
                "accepted": True,
                "completed": True,
                "points_written": 4,
                "planned_points": 4,
                "remaining_points": 0,
            },
            "minus": {
                "run_dir": str(tmp_path / "raw" / "minus"),
                "accepted": True,
                "completed": True,
                "points_written": 4,
                "planned_points": 4,
                "remaining_points": 0,
            },
        },
    }
    intake_path = package.package_dir / "result_intake.json"
    intake_path.write_text(json.dumps(intake), encoding="utf-8")
    (package.package_dir / "condition_snapshot.json").write_text(
        json.dumps(
            {
                "package_manifest_path": str(package.manifest_path),
                "result_intake_json_path": str(intake_path),
                "runs": [{"run_key": "longitudinal"}, {"run_key": "plus"}, {"run_key": "minus"}],
            }
        ),
        encoding="utf-8",
    )
    (package.package_dir / "condition_drift.json").write_text(
        json.dumps(
            {
                "package_manifest_path": str(package.manifest_path),
                "result_intake_json_path": str(intake_path),
                "accepted": True,
                "issues": [],
                "runs": {},
            }
        ),
        encoding="utf-8",
    )

    payload = write_dual_gate_lockin_hall_suite_lab_return_manifest(
        package.package_dir,
        operator_note="lab laptop run completed",
    )

    manifest_dir = package.package_dir / "lab_return"
    saved = json.loads((manifest_dir / "lab_return_manifest.json").read_text(encoding="utf-8"))
    report = (manifest_dir / "lab_return_manifest.md").read_text(encoding="utf-8")
    assert payload["ready_for_analysis"] is True
    assert saved["operator_note"] == "lab laptop run completed"
    assert saved["result_intake_accepted"] is True
    assert saved["condition_snapshot_written"] is True
    assert saved["condition_drift_accepted"] is True
    assert saved["package_manifest_sha256"]
    assert set(saved["runs"]) == {"longitudinal", "plus", "minus"}
    assert "Ready for analysis: True" in report


def test_hall_lifecycle_status_tracks_handoff_and_return_progress(tmp_path):
    package = _write_small_hall_package(tmp_path)

    initial = inspect_dual_gate_lockin_hall_suite_lifecycle_status(package.package_dir)
    assert initial["state"] == "package_ready"
    assert initial["measurement_conditions_ready"] is True
    assert initial["ready_for_lab_handoff"] is False
    initial_stage_by_key = {stage["key"]: stage for stage in initial["stages"]}
    assert initial_stage_by_key["measurement_condition_audits"]["ok"] is True
    assert initial_stage_by_key["keithley_parameter_audits"]["ok"] is True
    assert initial_stage_by_key["lockin_setting_audits"]["ok"] is True

    write_dual_gate_lockin_hall_suite_handoff_summary(package.package_dir)
    handoff = inspect_dual_gate_lockin_hall_suite_lifecycle_status(package.package_dir)
    handoff_text = format_dual_gate_lockin_hall_suite_lifecycle_status(handoff)
    assert handoff["state"] == "ready_for_lab_handoff"
    assert handoff["ready_for_lab_handoff"] is True
    assert "Lifecycle state: ready_for_lab_handoff" in handoff_text
    assert "| Lab handoff summary | PASS |" in handoff_text

    intake_path = package.package_dir / "result_intake.json"
    intake_path.write_text(
        json.dumps(
            {
                "package_manifest_path": str(package.manifest_path),
                "accepted": True,
                "issues": [],
                "runs": {
                    "longitudinal": {"run_dir": "data/raw/vxx", "accepted": True},
                    "plus": {"run_dir": "data/raw/plus", "accepted": True},
                    "minus": {"run_dir": "data/raw/minus", "accepted": True},
                },
            }
        ),
        encoding="utf-8",
    )
    pending = inspect_dual_gate_lockin_hall_suite_lifecycle_status(package.package_dir)
    assert pending["state"] == "condition_snapshot_pending"
    assert pending["ready_for_analysis"] is False
    (package.package_dir / "condition_snapshot.json").write_text(
        json.dumps(
            {
                "package_manifest_path": str(package.manifest_path),
                "result_intake_json_path": str(intake_path),
                "runs": [{"run_key": "longitudinal"}, {"run_key": "plus"}, {"run_key": "minus"}],
            }
        ),
        encoding="utf-8",
    )
    drift_pending = inspect_dual_gate_lockin_hall_suite_lifecycle_status(package.package_dir)
    assert drift_pending["state"] == "condition_drift_pending"
    (package.package_dir / "condition_drift.json").write_text(
        json.dumps(
            {
                "package_manifest_path": str(package.manifest_path),
                "result_intake_json_path": str(intake_path),
                "accepted": True,
                "issues": [],
                "runs": {},
            }
        ),
        encoding="utf-8",
    )
    write_dual_gate_lockin_hall_suite_lab_return_manifest(package.package_dir)
    returned = inspect_dual_gate_lockin_hall_suite_lifecycle_status(package.package_dir)
    returned_stage_by_key = {stage["key"]: stage for stage in returned["stages"]}
    assert returned["state"] == "ready_for_analysis"
    assert returned["ready_for_analysis"] is True
    assert returned_stage_by_key["condition_snapshot"]["ok"] is True
    assert returned_stage_by_key["condition_drift"]["ok"] is True


def test_hall_lifecycle_status_blocks_handoff_when_measurement_condition_audit_regresses(tmp_path):
    package = _write_small_hall_package(tmp_path)
    write_dual_gate_lockin_hall_suite_handoff_summary(package.package_dir)
    manifest = json.loads(package.manifest_path.read_text(encoding="utf-8"))
    manifest["measurement_condition_audits"]["ok_for_hardware"] = False
    manifest["measurement_condition_audits"]["records"][0]["ok_for_hardware"] = False
    package.manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    payload = inspect_dual_gate_lockin_hall_suite_lifecycle_status(package.package_dir)
    text = format_dual_gate_lockin_hall_suite_lifecycle_status(payload)
    stage_by_key = {stage["key"]: stage for stage in payload["stages"]}

    assert payload["state"] == "measurement_condition_review"
    assert payload["measurement_conditions_ready"] is False
    assert payload["ready_for_lab_handoff"] is False
    assert stage_by_key["measurement_condition_audits"]["ok"] is False
    assert "| Measurement-condition audits | REVIEW |" in text


def test_hall_lifecycle_status_blocks_analysis_when_condition_drift_fails(tmp_path):
    package = _write_small_hall_package(tmp_path)
    write_dual_gate_lockin_hall_suite_handoff_summary(package.package_dir)
    intake_path = package.package_dir / "result_intake.json"
    intake_path.write_text(
        json.dumps(
            {
                "package_manifest_path": str(package.manifest_path),
                "accepted": True,
                "issues": [],
                "runs": {
                    "longitudinal": {"run_dir": "data/raw/vxx", "accepted": True},
                    "plus": {"run_dir": "data/raw/plus", "accepted": True},
                    "minus": {"run_dir": "data/raw/minus", "accepted": True},
                },
            }
        ),
        encoding="utf-8",
    )
    (package.package_dir / "condition_snapshot.json").write_text(
        json.dumps(
            {
                "package_manifest_path": str(package.manifest_path),
                "result_intake_json_path": str(intake_path),
                "runs": [{"run_key": "longitudinal"}, {"run_key": "plus"}, {"run_key": "minus"}],
            }
        ),
        encoding="utf-8",
    )
    (package.package_dir / "condition_drift.json").write_text(
        json.dumps(
            {
                "package_manifest_path": str(package.manifest_path),
                "result_intake_json_path": str(intake_path),
                "accepted": False,
                "issues": [
                    {
                        "severity": "error",
                        "run_key": "plus",
                        "field": "gate1_instrument.nplc",
                        "expected": 1.0,
                        "actual": 3.0,
                        "message": "acquisition condition differs from packaged recipe",
                    }
                ],
                "runs": {},
            }
        ),
        encoding="utf-8",
    )
    write_dual_gate_lockin_hall_suite_lab_return_manifest(package.package_dir)

    payload = inspect_dual_gate_lockin_hall_suite_lifecycle_status(package.package_dir)
    text = format_dual_gate_lockin_hall_suite_lifecycle_status(payload)
    stage_by_key = {stage["key"]: stage for stage in payload["stages"]}

    assert payload["state"] == "acquisition_condition_drift"
    assert payload["ready_for_analysis"] is False
    assert stage_by_key["condition_drift"]["ok"] is False
    assert "| Acquisition-condition drift | REVIEW |" in text


def test_hall_workflow_rehearsal_runs_direct_module_api(tmp_path):
    package = _write_small_hall_package(tmp_path)
    manifest = json.loads(package.manifest_path.read_text(encoding="utf-8"))
    manifest["approved_next_scan"] = {"strategy": "refine_charge_neutrality_region"}
    package.manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    payload = run_dual_gate_lockin_hall_suite_approved_next_scan_rehearsal(
        package.package_dir,
        output_dir=None,
        fake_gate1_leak_resistance_ohm=1_000_000_000.0,
        fake_gate2_leak_resistance_ohm=1_000_000_000.0,
        fake_lockin_r_v=2e-6,
        fake_lockin_phase_deg=0.0,
        fake_noise_std_v=0.0,
        safety_dir="configs/safety",
        overwrite=False,
    )

    assert payload["completed"] is True
    assert set(payload["runs"]) == {"longitudinal", "plus", "minus", "zero"}
    assert (package.package_dir / "dry_run_rehearsal" / "rehearsal_summary.json").exists()
    assert (package.package_dir / "dry_run_rehearsal" / "hall_analysis" / "hall_suite_analysis_review.json").exists()
    status = inspect_dual_gate_lockin_hall_suite_workflow_status(package.manifest_path)
    stage_by_key = {stage["key"]: stage for stage in status["stages"]}
    assert stage_by_key["keithley_parameter_audits"]["ok"] is True
    assert stage_by_key["lockin_setting_audits"]["ok"] is True
    assert stage_by_key["dry_run_rehearsal"]["ok"] is True


def test_hall_workflow_rehearsal_requires_approved_next_scan(tmp_path):
    package_dir = tmp_path / "package"
    package_dir.mkdir()
    (package_dir / "package_manifest.json").write_text(
        json.dumps({"package_name": "no_approval", "copied_recipes": {}}),
        encoding="utf-8",
    )

    try:
        run_dual_gate_lockin_hall_suite_approved_next_scan_rehearsal(
            package_dir,
            output_dir=None,
            fake_gate1_leak_resistance_ohm=1_000_000_000.0,
            fake_gate2_leak_resistance_ohm=1_000_000_000.0,
            fake_lockin_r_v=2e-6,
            fake_lockin_phase_deg=0.0,
            fake_noise_std_v=0.0,
            safety_dir="configs/safety",
            overwrite=False,
        )
    except ValueError as exc:
        assert "approved_next_scan" in str(exc)
    else:
        raise AssertionError("Expected ValueError")


def _shrink_suite_recipes(paths):
    for path in paths:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        data["gate1_sweep"]["points"] = 2
        data["gate2_sweep"]["points"] = 2
        data["gate1_sweep"]["settle_s"] = 0.0
        data["gate2_sweep"]["settle_s"] = 0.0
        data["lockin"]["read_settle_s"] = 0.0
        path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def _write_small_hall_package(tmp_path):
    template = write_dual_gate_lockin_hall_suite_template(
        "configs/recipes/dual_gate_lockin_four_terminal_dry_run.yaml",
        tmp_path / "suite",
        measurement_prefix="workflow_graphene",
        magnetic_field_t=1.0,
        run_output_directory=tmp_path / "raw",
    )
    _shrink_suite_recipes(
        [
            template.longitudinal_recipe,
            template.plus_hall_recipe,
            template.minus_hall_recipe,
            template.zero_hall_recipe,
        ]
    )
    return write_dual_gate_lockin_hall_suite_acquisition_package(
        template.longitudinal_recipe,
        template.plus_hall_recipe,
        template.minus_hall_recipe,
        tmp_path / "packages",
        zero_hall_recipe=template.zero_hall_recipe,
        package_name="workflow_graphene_package",
        chunk_size=5,
    )


def _write_four_terminal_ac_smoke_intake_json(tmp_path, *, accepted=True):
    path = tmp_path / ("four_terminal_ac_smoke_intake_pass.json" if accepted else "four_terminal_ac_smoke_intake_fail.json")
    payload = {
        "accepted": accepted,
        "measurement_name": "four_terminal_ac_smoke",
        "measurement_geometry": "four_terminal, 4-terminal",
        "hardware_guard_required": True,
        "hardware_guard_present": True,
        "hardware_guard_accepted": True,
        "hardware_guard_approval_note": "fixture checked; SR860 A-B verified",
        "hardware_guard_point_count": 3,
        "hardware_guard_max_points": 3,
        "lockin_voltage_input": "a-b",
        "topology_excitation_contacts": ["S", "D"],
        "topology_lockin_input_contacts": ["Vxx+", "Vxx-"],
        "source_nplc": 1.0,
        "source_voltage_range_v": 0.02,
        "source_current_range_a": 1.0e-7,
        "source_current_compliance_a": 1.0e-7,
        "issues": [] if accepted else [{"severity": "error", "check": "synthetic", "message": "failed"}],
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path
