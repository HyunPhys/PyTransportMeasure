import json

import yaml

from pytransport.dual_gate_lockin_hall_suite import (
    write_dual_gate_lockin_hall_suite_acquisition_package,
    write_dual_gate_lockin_hall_suite_template,
)
from pytransport.hall_workflow import (
    format_dual_gate_lockin_hall_suite_package_validation,
    format_dual_gate_lockin_hall_suite_workflow_status,
    inspect_dual_gate_lockin_hall_suite_workflow_status,
    run_dual_gate_lockin_hall_suite_approved_next_scan_rehearsal,
    validate_dual_gate_lockin_hall_suite_package_manifest,
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


def test_hall_package_validator_reports_missing_audit_artifact(tmp_path):
    package = _write_small_hall_package(tmp_path)
    missing = package.package_dir / "keithley_audit" / "longitudinal_keithley_audit.json"
    missing.unlink()

    payload = validate_dual_gate_lockin_hall_suite_package_manifest(package.manifest_path)

    assert payload["valid"] is False
    assert any(issue["code"] == "missing_audit_record_json" for issue in payload["issues"])
    assert any(issue["path"] == str(missing) for issue in payload["issues"])


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
