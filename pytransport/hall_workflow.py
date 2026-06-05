"""Hall-suite workflow orchestration helpers.

These helpers keep hardware-free rehearsal and read-only workflow status logic
outside the CLI so GUI/API layers can reuse the same core behavior.
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from hashlib import sha256
from pathlib import Path

import yaml

from .dual_gate_lockin import run_dual_gate_lockin_sweep
from .dual_gate_lockin_hall_suite import (
    write_dual_gate_lockin_hall_suite_analysis,
    write_dual_gate_lockin_hall_suite_analysis_review,
    write_dual_gate_lockin_hall_suite_next_scan_proposal,
    write_dual_gate_lockin_hall_suite_result_intake,
)
from .instruments.fake import DualGateFakeDeviceState, DualGateFakeLockIn, DualGateFakeSMU
from .recipes import OutputConfig, load_dual_gate_lockin_recipe, load_named_safety_preset


def validate_dual_gate_lockin_hall_suite_package_manifest(package_manifest_or_dir: Path) -> dict:
    manifest_path = _resolve_package_manifest_path(package_manifest_or_dir)
    package_dir = manifest_path.parent
    manifest = _load_json_object(manifest_path)
    checks: list[dict] = []
    issues: list[dict] = []

    def add_check(
        key: str,
        label: str,
        *,
        ok: bool,
        path: Path | None = None,
        details: str = "",
        code: str | None = None,
        severity: str = "error",
        message: str | None = None,
    ) -> None:
        checks.append(
            {
                "key": key,
                "label": label,
                "ok": bool(ok),
                "path": str(path) if path is not None else None,
                "details": details,
            }
        )
        if not ok:
            issues.append(
                {
                    "severity": severity,
                    "code": code or key,
                    "message": message or details or label,
                    "path": str(path) if path is not None else None,
                }
            )

    def add_warning(code: str, message: str, *, path: Path | None = None) -> None:
        issues.append({"severity": "warning", "code": code, "message": message, "path": str(path) if path else None})

    schema_version = manifest.get("manifest_schema_version")
    add_check(
        "manifest_schema_version",
        "Manifest schema version",
        ok=schema_version == 2,
        path=manifest_path,
        details=f"schema={schema_version!r}",
        code="unsupported_manifest_schema_version",
        message="package_manifest.json should declare manifest_schema_version: 2",
    )
    if schema_version is None:
        add_warning("legacy_manifest_schema", "legacy package manifest has no manifest_schema_version", path=manifest_path)
    add_check(
        "package_name",
        "Package name",
        ok=bool(manifest.get("package_name")),
        path=manifest_path,
        details=str(manifest.get("package_name") or "missing"),
        code="missing_package_name",
    )
    add_check(
        "runbook",
        "Acquisition runbook",
        ok=(package_dir / "acquisition_runbook.md").exists(),
        path=package_dir / "acquisition_runbook.md",
        details="required for lab handoff",
        code="missing_acquisition_runbook",
    )
    add_check(
        "zip",
        "Package ZIP",
        ok=package_dir.with_suffix(".zip").exists(),
        path=package_dir.with_suffix(".zip"),
        details="portable lab handoff archive",
        code="missing_package_zip",
    )

    copied_recipes = manifest.get("copied_recipes")
    copied_ok = isinstance(copied_recipes, dict)
    add_check(
        "copied_recipes",
        "Copied recipe manifest",
        ok=copied_ok,
        path=manifest_path,
        details="copied_recipes object present" if copied_ok else "missing copied_recipes object",
        code="missing_copied_recipes",
    )
    recipe_count = 0
    if isinstance(copied_recipes, dict):
        for key in ["longitudinal", "plus", "minus"]:
            recipe_count += _validate_manifest_path(
                copied_recipes.get(key),
                package_dir,
                checks,
                issues,
                key=f"recipe_{key}",
                label=f"Copied {key} recipe",
                code=f"missing_{key}_recipe",
                required=True,
            )
        if copied_recipes.get("zero"):
            recipe_count += _validate_manifest_path(
                copied_recipes.get("zero"),
                package_dir,
                checks,
                issues,
                key="recipe_zero",
                label="Copied zero-field Hall recipe",
                code="missing_zero_recipe",
                required=True,
            )
    measurement_condition_audits = manifest.get("measurement_condition_audits")
    if isinstance(measurement_condition_audits, dict):
        _validate_measurement_condition_audits(measurement_condition_audits, package_dir, checks, issues)
    else:
        add_check(
            "measurement_condition_audits",
            "Measurement-condition audits",
            ok=False,
            path=manifest_path,
            details="missing normalized measurement_condition_audits block",
            code="missing_measurement_condition_audits",
        )
        _validate_legacy_audit_block(
            manifest.get("keithley_parameter_audits"),
            package_dir,
            checks,
            issues,
            block_key="keithley_parameter_audits",
            label="Legacy Keithley parameter audits",
            instrument="keithley_2450",
        )
        _validate_legacy_audit_block(
            manifest.get("lockin_setting_audits"),
            package_dir,
            checks,
            issues,
            block_key="lockin_setting_audits",
            label="Legacy SR860 setting audits",
            instrument="srs_sr860",
        )

    valid = not any(issue["severity"] == "error" for issue in issues)
    return {
        "package_dir": str(package_dir),
        "package_manifest": str(manifest_path),
        "package_name": manifest.get("package_name"),
        "manifest_schema_version": schema_version,
        "recipe_count": recipe_count,
        "valid": valid,
        "checks": checks,
        "issues": issues,
    }


def format_dual_gate_lockin_hall_suite_package_validation(payload: dict) -> str:
    lines = [
        "Dual-gate lock-in Hall suite package validation",
        f"Package: {payload.get('package_name') or 'n/a'}",
        f"Manifest: {payload.get('package_manifest')}",
        f"Valid for lab handoff: {payload.get('valid')}",
        "",
        "| Check | Status | Path | Details |",
        "| --- | --- | --- | --- |",
    ]
    for check in payload.get("checks", []):
        status = "PASS" if check.get("ok") else "FAIL"
        lines.append(f"| {check.get('label')} | {status} | `{check.get('path') or 'n/a'}` | {check.get('details') or ''} |")
    issues = payload.get("issues", [])
    if issues:
        lines.extend(["", "## Issues", ""])
        for issue in issues:
            lines.append(f"- {issue.get('severity', 'error').upper()} {issue.get('code')}: {issue.get('message')}")
    return "\n".join(lines)


def write_dual_gate_lockin_hall_suite_lab_smoke_bundle(
    package_manifest_or_dir: Path,
    *,
    output_dir: Path | None = None,
    safety_dir: Path = Path("configs/safety"),
    overwrite: bool = False,
) -> dict:
    validation = validate_dual_gate_lockin_hall_suite_package_manifest(package_manifest_or_dir)
    if not validation["valid"]:
        raise ValueError("package validation failed; run validate-package and fix issues before smoke bundle generation")
    package_dir = Path(validation["package_dir"])
    manifest_path = Path(validation["package_manifest"])
    manifest = _load_json_object(manifest_path)
    recipe_paths = _package_recipe_paths(manifest, package_dir)
    recipes = {key: load_dual_gate_lockin_recipe(path) for key, path in recipe_paths.items()}
    out = output_dir or package_dir / "lab_smoke"
    if out.exists() and not overwrite:
        raise FileExistsError(f"Lab smoke bundle already exists: {out}")
    out.mkdir(parents=True, exist_ok=True)

    instruments = _hall_suite_smoke_instrument_records(recipes)
    commands = {
        "package_validation": [
            f"ptm dual-gate-lockin-hall-suite-validate-package {package_dir} --json-output {out / 'package_validation.json'}"
        ],
        "visa_discovery": ["ptm list-resources"],
        "identify": [
            f"ptm identify --instrument {record['instrument']} --address \"{record['address']}\""
            for record in instruments
        ],
        "probe": [
            f"ptm probe --instrument {record['instrument']} --address \"{record['address']}\""
            for record in instruments
        ],
        "preflight": [
            f"ptm dual-gate-lockin-preflight {path} --safety-dir {safety_dir}"
            for path in recipe_paths.values()
        ],
        "suite_checks": [
            _hall_suite_check_command(recipe_paths),
            _hall_suite_plan_command(recipe_paths),
        ],
    }
    payload = {
        "package_dir": str(package_dir),
        "package_manifest": str(manifest_path),
        "package_name": manifest.get("package_name"),
        "output_dir": str(out),
        "safety_dir": str(safety_dir),
        "instrument_count": len(instruments),
        "instruments": instruments,
        "recipe_paths": {key: str(path) for key, path in recipe_paths.items()},
        "commands": commands,
        "completed": True,
    }
    json_path = out / "lab_smoke_bundle.json"
    report_path = out / "lab_smoke_checklist.md"
    validation_json_path = out / "package_validation.json"
    validation_json_path.write_text(json.dumps(validation, indent=2, sort_keys=True), encoding="utf-8")
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(format_dual_gate_lockin_hall_suite_lab_smoke_bundle(payload), encoding="utf-8")
    payload["json_path"] = str(json_path)
    payload["report_path"] = str(report_path)
    payload["package_validation_json_path"] = str(validation_json_path)
    return payload


def format_dual_gate_lockin_hall_suite_lab_smoke_bundle(payload: dict) -> str:
    commands = payload.get("commands", {})
    return "\n".join(
        [
            "# Hall Suite Lab Handoff Smoke Checklist",
            "",
            f"- Package: `{payload.get('package_dir')}`",
            f"- Manifest: `{payload.get('package_manifest')}`",
            f"- Safety dir: `{payload.get('safety_dir')}`",
            "",
            "## Instruments",
            "",
            "| Role | Instrument | Address | Recipes |",
            "| --- | --- | --- | --- |",
            *[
                (
                    f"| {record.get('role')} | {record.get('instrument')} | "
                    f"`{record.get('address')}` | {', '.join(record.get('recipe_keys', []))} |"
                )
                for record in payload.get("instruments", [])
            ],
            "",
            "## 1. Package Validation",
            "",
            "```powershell",
            *commands.get("package_validation", []),
            "```",
            "",
            "## 2. VISA Discovery",
            "",
            "```powershell",
            *commands.get("visa_discovery", []),
            "```",
            "",
            "## 3. Read-Only Identify",
            "",
            "```powershell",
            *commands.get("identify", []),
            "```",
            "",
            "## 4. Read-Only Probe",
            "",
            "```powershell",
            *commands.get("probe", []),
            "```",
            "",
            "## 5. Suite Checks",
            "",
            "```powershell",
            *commands.get("suite_checks", []),
            "```",
            "",
            "## 6. Per-Recipe Preflight",
            "",
            "```powershell",
            *commands.get("preflight", []),
            "```",
            "",
            "## Pass Criteria",
            "",
            "- Package validation prints `Valid for lab handoff: True`.",
            "- `ptm list-resources` shows the two Keithley addresses and SR860 address.",
            "- Every Keithley identify response contains `MODEL 2450`.",
            "- SR860 identify response contains `SR860`.",
            "- Every probe completes without communication errors.",
            "- Every dual-gate lock-in preflight reports OK before any hardware output command is run.",
            "",
        ]
    )


def review_dual_gate_lockin_hall_suite_hardware_commands(package_manifest_or_dir: Path) -> dict:
    validation = validate_dual_gate_lockin_hall_suite_package_manifest(package_manifest_or_dir)
    if not validation["valid"]:
        raise ValueError("package validation failed; fix package before hardware command review")
    package_dir = Path(validation["package_dir"])
    manifest_path = Path(validation["package_manifest"])
    manifest = _load_json_object(manifest_path)
    runbook_path = package_dir / "acquisition_runbook.md"
    commands = _extract_active_dual_gate_lockin_commands(runbook_path)
    checks: list[dict] = []
    issues: list[dict] = []
    expected_chunk_size = manifest.get("chunk_size")
    expected_max_hardware_points = manifest.get("max_hardware_points")

    if not commands:
        issues.append(
            {
                "severity": "error",
                "code": "missing_active_hardware_commands",
                "message": "acquisition_runbook.md contains no active dual-gate-lockin hardware commands",
                "path": str(runbook_path),
            }
        )
    for index, command in enumerate(commands):
        flags = _command_flag_values(command)
        command_checks = [
            _hardware_command_flag_check(command, flags, "--allow-active-sweep", required_value=None),
            _hardware_command_flag_check(command, flags, "--stop-after-new-points", required_value=expected_chunk_size),
            _hardware_command_flag_check(command, flags, "--max-hardware-points", required_value=expected_max_hardware_points),
            _hardware_command_flag_check(command, flags, "--hardware-approval-note", required_value=None),
            _hardware_command_flag_check(command, flags, "--accepted-previous-run", required_value=None),
        ]
        ok = all(check["ok"] for check in command_checks)
        checks.append(
            {
                "key": f"hardware_command_{index}",
                "label": f"Hardware command {index + 1}",
                "ok": ok,
                "command": command,
                "checks": command_checks,
            }
        )
        for check in command_checks:
            if not check["ok"]:
                issues.append(
                    {
                        "severity": "error",
                        "code": check["code"],
                        "message": f"Hardware command {index + 1}: {check['message']}",
                        "path": str(runbook_path),
                    }
                )
    valid = not any(issue["severity"] == "error" for issue in issues)
    return {
        "package_dir": str(package_dir),
        "package_manifest": str(manifest_path),
        "package_name": manifest.get("package_name"),
        "runbook": str(runbook_path),
        "expected_chunk_size": expected_chunk_size,
        "expected_max_hardware_points": expected_max_hardware_points,
        "command_count": len(commands),
        "valid": valid,
        "checks": checks,
        "issues": issues,
    }


def format_dual_gate_lockin_hall_suite_hardware_command_review(payload: dict) -> str:
    lines = [
        "Dual-gate lock-in Hall suite hardware command review",
        f"Package: {payload.get('package_name') or 'n/a'}",
        f"Runbook: {payload.get('runbook')}",
        f"Hardware commands guarded: {payload.get('valid')}",
        "",
        "| Command | Status | Details |",
        "| --- | --- | --- |",
    ]
    for check in payload.get("checks", []):
        failed = [item for item in check.get("checks", []) if not item.get("ok")]
        details = "all required guards present" if not failed else ", ".join(item["flag"] for item in failed)
        lines.append(f"| {check.get('label')} | {'PASS' if check.get('ok') else 'FAIL'} | {details} |")
    issues = payload.get("issues", [])
    if issues:
        lines.extend(["", "## Issues", ""])
        for issue in issues:
            lines.append(f"- {issue.get('severity', 'error').upper()} {issue.get('code')}: {issue.get('message')}")
    return "\n".join(lines)


def write_dual_gate_lockin_hall_suite_handoff_summary(
    package_manifest_or_dir: Path,
    *,
    output_dir: Path | None = None,
    safety_dir: Path = Path("configs/safety"),
    overwrite: bool = False,
) -> dict:
    validation = validate_dual_gate_lockin_hall_suite_package_manifest(package_manifest_or_dir)
    package_dir = Path(validation["package_dir"])
    out = output_dir or package_dir / "handoff_summary"
    if out.exists() and not overwrite:
        raise FileExistsError(f"Hall handoff summary already exists: {out}")
    out.mkdir(parents=True, exist_ok=True)

    smoke = write_dual_gate_lockin_hall_suite_lab_smoke_bundle(
        package_dir,
        output_dir=out / "lab_smoke",
        safety_dir=safety_dir,
        overwrite=True,
    )
    hardware_review = review_dual_gate_lockin_hall_suite_hardware_commands(package_dir)
    package_validation_path = out / "package_validation.json"
    smoke_json_path = out / "lab_smoke_bundle.json"
    hardware_review_path = out / "hardware_command_review.json"
    package_validation_path.write_text(json.dumps(validation, indent=2, sort_keys=True), encoding="utf-8")
    smoke_json_path.write_text(json.dumps(smoke, indent=2, sort_keys=True), encoding="utf-8")
    hardware_review_path.write_text(json.dumps(hardware_review, indent=2, sort_keys=True), encoding="utf-8")

    pass_state = bool(validation.get("valid")) and bool(smoke.get("completed")) and bool(hardware_review.get("valid"))
    payload = {
        "package_dir": str(package_dir),
        "package_manifest": validation.get("package_manifest"),
        "package_name": validation.get("package_name"),
        "output_dir": str(out),
        "pass": pass_state,
        "checks": {
            "package_validation": bool(validation.get("valid")),
            "lab_smoke_bundle": bool(smoke.get("completed")),
            "hardware_command_review": bool(hardware_review.get("valid")),
        },
        "artifacts": {
            "package_validation_json": str(package_validation_path),
            "lab_smoke_bundle_json": str(smoke_json_path),
            "lab_smoke_checklist": smoke.get("report_path"),
            "hardware_command_review_json": str(hardware_review_path),
        },
        "issue_count": len(validation.get("issues", [])) + len(hardware_review.get("issues", [])),
    }
    json_path = out / "handoff_summary.json"
    report_path = out / "handoff_summary.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(format_dual_gate_lockin_hall_suite_handoff_summary(payload), encoding="utf-8")
    payload["json_path"] = str(json_path)
    payload["report_path"] = str(report_path)
    return payload


def format_dual_gate_lockin_hall_suite_handoff_summary(payload: dict) -> str:
    checks = payload.get("checks", {})
    artifacts = payload.get("artifacts", {})
    lines = [
        "# Hall Suite Lab Handoff Summary",
        "",
        f"- Package: `{payload.get('package_dir')}`",
        f"- Manifest: `{payload.get('package_manifest')}`",
        f"- Ready for lab handoff: {payload.get('pass')}",
        "",
        "| Check | Status |",
        "| --- | --- |",
        f"| Package validation | {'PASS' if checks.get('package_validation') else 'REVIEW'} |",
        f"| Lab smoke bundle | {'PASS' if checks.get('lab_smoke_bundle') else 'REVIEW'} |",
        f"| Hardware command review | {'PASS' if checks.get('hardware_command_review') else 'REVIEW'} |",
        "",
        "## Artifacts",
        "",
        f"- Package validation JSON: `{artifacts.get('package_validation_json')}`",
        f"- Lab smoke checklist: `{artifacts.get('lab_smoke_checklist')}`",
        f"- Lab smoke bundle JSON: `{artifacts.get('lab_smoke_bundle_json')}`",
        f"- Hardware command review JSON: `{artifacts.get('hardware_command_review_json')}`",
        "",
        "## Lab Use",
        "",
        "Attach this summary to the lab notebook entry for the package. Run the lab smoke checklist on the lab laptop before any active hardware command.",
        "",
    ]
    return "\n".join(lines)


def write_dual_gate_lockin_hall_suite_lab_return_manifest(
    package_manifest_or_dir: Path,
    *,
    result_intake_json: Path | None = None,
    output_dir: Path | None = None,
    operator_note: str | None = None,
    overwrite: bool = False,
) -> dict:
    manifest_path = _resolve_package_manifest_path(package_manifest_or_dir)
    package_dir = manifest_path.parent
    intake_path = result_intake_json or package_dir / "result_intake.json"
    intake = _load_json_object(intake_path)
    if "accepted" not in intake:
        raise ValueError(f"{intake_path} is missing accepted")
    runs = intake.get("runs")
    if not isinstance(runs, dict):
        raise ValueError(f"{intake_path} is missing runs")
    out = output_dir or package_dir / "lab_return"
    if out.exists() and not overwrite:
        raise FileExistsError(f"Lab return manifest output already exists: {out}")
    out.mkdir(parents=True, exist_ok=True)
    package_zip = package_dir.with_suffix(".zip")
    run_records = {
        key: {
            "run_dir": record.get("run_dir"),
            "accepted": record.get("accepted"),
            "completed": record.get("completed"),
            "points_written": record.get("points_written"),
            "planned_points": record.get("planned_points"),
            "remaining_points": record.get("remaining_points"),
        }
        for key, record in runs.items()
        if isinstance(record, dict)
    }
    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "package_dir": str(package_dir),
        "package_manifest": str(manifest_path),
        "package_manifest_sha256": _sha256_file(manifest_path),
        "package_zip": str(package_zip) if package_zip.exists() else None,
        "package_zip_sha256": _sha256_file(package_zip) if package_zip.exists() else None,
        "result_intake_json": str(intake_path),
        "result_intake_accepted": bool(intake.get("accepted")),
        "result_intake_issue_count": len(intake.get("issues", [])) if isinstance(intake.get("issues"), list) else None,
        "runs": run_records,
        "operator_note": operator_note,
        "ready_for_analysis": bool(intake.get("accepted")),
    }
    json_path = out / "lab_return_manifest.json"
    report_path = out / "lab_return_manifest.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(format_dual_gate_lockin_hall_suite_lab_return_manifest(payload), encoding="utf-8")
    payload["json_path"] = str(json_path)
    payload["report_path"] = str(report_path)
    return payload


def format_dual_gate_lockin_hall_suite_lab_return_manifest(payload: dict) -> str:
    lines = [
        "# Hall Suite Lab Return Manifest",
        "",
        f"- Package: `{payload.get('package_dir')}`",
        f"- Manifest SHA256: `{payload.get('package_manifest_sha256')}`",
        f"- Result intake: `{payload.get('result_intake_json')}`",
        f"- Intake accepted: {payload.get('result_intake_accepted')}",
        f"- Ready for analysis: {payload.get('ready_for_analysis')}",
        f"- Operator note: {payload.get('operator_note') or 'n/a'}",
        "",
        "| Role | Run folder | Accepted | Completed | Points | Remaining |",
        "| --- | --- | --- | --- | ---: | ---: |",
    ]
    for key, record in payload.get("runs", {}).items():
        lines.append(
            f"| {key} | `{record.get('run_dir')}` | {record.get('accepted')} | "
            f"{record.get('completed')} | {record.get('points_written')}/{record.get('planned_points')} | "
            f"{record.get('remaining_points')} |"
        )
    lines.extend(
        [
            "",
            "## Lab Use",
            "",
            "Keep this manifest with the returned package folder. Continue to Hall analysis only when `Ready for analysis` is True.",
            "",
        ]
    )
    return "\n".join(lines)


def inspect_dual_gate_lockin_hall_suite_workflow_status(package_manifest_or_dir: Path) -> dict:
    manifest_path = _resolve_package_manifest_path(package_manifest_or_dir)
    package_dir = manifest_path.parent
    manifest = _load_json_object(manifest_path)
    stages = []

    def add_stage(key: str, label: str, path: Path | None, *, ok: bool | None = None, details: str = "") -> None:
        exists = path.exists() if path is not None else False
        passed = exists if ok is None else bool(ok)
        stages.append(
            {
                "key": key,
                "label": label,
                "exists": exists,
                "ok": passed,
                "path": str(path) if path is not None else None,
                "details": details,
            }
        )

    runbook = package_dir / "acquisition_runbook.md"
    zip_path = package_dir.with_suffix(".zip")
    add_stage("package_manifest", "Package manifest", manifest_path, ok=True, details=f"package={manifest.get('package_name', 'n/a')}")
    add_stage("runbook", "Acquisition runbook", runbook)
    add_stage("zip", "Package ZIP", zip_path)
    copied = manifest.get("copied_recipes") if isinstance(manifest.get("copied_recipes"), dict) else {}
    recipe_paths = []
    for key in ["longitudinal", "plus", "minus", "zero"]:
        value = copied.get(key)
        if value:
            path = Path(str(value))
            if not path.is_absolute():
                path = package_dir / path
            recipe_paths.append(path)
    add_stage(
        "recipes",
        "Copied recipes",
        package_dir / "recipes",
        ok=bool(recipe_paths) and all(path.exists() for path in recipe_paths),
        details=f"{len(recipe_paths)} recipes",
    )
    approved = manifest.get("approved_next_scan") if isinstance(manifest.get("approved_next_scan"), dict) else None
    add_stage(
        "approved_next_scan",
        "Approved next-scan provenance",
        manifest_path,
        ok=approved is not None,
        details=(approved or {}).get("strategy", "not present") if approved else "not present",
    )
    measurement_condition_audits = manifest.get("measurement_condition_audits")
    normalized_audit_records = (
        measurement_condition_audits.get("records")
        if isinstance(measurement_condition_audits, dict)
        else None
    )
    keithley_audits = manifest.get("keithley_parameter_audits")
    audit_paths: list[Path] = []
    audit_ok = False
    audit_details = "not present"
    if isinstance(normalized_audit_records, list):
        keithley_records = [
            record
            for record in normalized_audit_records
            if isinstance(record, dict) and record.get("instrument") == "keithley_2450"
        ]
        audit_paths = _audit_record_paths(keithley_records, package_dir)
        audit_ok = bool(audit_paths) and all(path.exists() for path in audit_paths) and all(
            bool(record.get("ok_for_hardware")) for record in keithley_records
        )
        audit_details = f"{len(keithley_records)} recipe audits"
    elif isinstance(keithley_audits, dict):
        for record in keithley_audits.values():
            if not isinstance(record, dict):
                continue
            for field in ["json", "markdown"]:
                value = record.get(field)
                if value:
                    path = Path(str(value))
                    if not path.is_absolute():
                        path = package_dir / path
                    audit_paths.append(path)
        audit_ok = bool(audit_paths) and all(path.exists() for path in audit_paths) and all(
            bool(record.get("ok_for_hardware"))
            for record in keithley_audits.values()
            if isinstance(record, dict)
        )
        audit_details = f"{len(keithley_audits)} recipe audits"
    add_stage(
        "keithley_parameter_audits",
        "Keithley parameter audits",
        package_dir / "keithley_audit",
        ok=audit_ok,
        details=audit_details,
    )
    lockin_audits = manifest.get("lockin_setting_audits")
    lockin_audit_paths: list[Path] = []
    lockin_audit_ok = False
    lockin_audit_details = "not present"
    if isinstance(normalized_audit_records, list):
        lockin_records = [
            record
            for record in normalized_audit_records
            if isinstance(record, dict) and record.get("instrument") == "srs_sr860"
        ]
        lockin_audit_paths = _audit_record_paths(lockin_records, package_dir)
        lockin_audit_ok = bool(lockin_audit_paths) and all(path.exists() for path in lockin_audit_paths) and all(
            bool(record.get("ok_for_hardware")) for record in lockin_records
        )
        lockin_audit_details = f"{len(lockin_records)} recipe audits"
    elif isinstance(lockin_audits, dict):
        for record in lockin_audits.values():
            if not isinstance(record, dict):
                continue
            for field in ["json", "markdown"]:
                value = record.get(field)
                if value:
                    path = Path(str(value))
                    if not path.is_absolute():
                        path = package_dir / path
                    lockin_audit_paths.append(path)
        lockin_audit_ok = bool(lockin_audit_paths) and all(path.exists() for path in lockin_audit_paths) and all(
            bool(record.get("ok_for_hardware"))
            for record in lockin_audits.values()
            if isinstance(record, dict)
        )
        lockin_audit_details = f"{len(lockin_audits)} recipe audits"
    add_stage(
        "lockin_setting_audits",
        "SR860 setting audits",
        package_dir / "lockin_audit",
        ok=lockin_audit_ok,
        details=lockin_audit_details,
    )

    intake_json = package_dir / "result_intake.json"
    intake_ok = False
    if intake_json.exists():
        try:
            intake_ok = _load_json_object(intake_json).get("accepted") is True
        except ValueError:
            intake_ok = False
    add_stage("result_intake", "Result intake", intake_json, ok=intake_ok if intake_json.exists() else False)
    analysis_dir = package_dir / "hall_analysis"
    analysis_manifest = analysis_dir / "hall_suite_analysis_manifest.json"
    add_stage("analysis", "Hall analysis", analysis_manifest)
    review_json = analysis_dir / "hall_suite_analysis_review.json"
    review_ok = False
    if review_json.exists():
        try:
            review_ok = _load_json_object(review_json).get("accepted_for_next_scan_decision") is True
        except ValueError:
            review_ok = False
    add_stage("analysis_review", "Analysis review", review_json, ok=review_ok if review_json.exists() else False)
    proposal_json = analysis_dir / "hall_suite_next_scan_proposal.json"
    add_stage("next_proposal", "Next-scan proposal", proposal_json)

    rehearsal_dir = package_dir / "dry_run_rehearsal"
    rehearsal_json = rehearsal_dir / "rehearsal_summary.json"
    rehearsal_ok = False
    if rehearsal_json.exists():
        try:
            rehearsal_ok = _load_json_object(rehearsal_json).get("completed") is True
        except ValueError:
            rehearsal_ok = False
    add_stage("dry_run_rehearsal", "Dry-run rehearsal", rehearsal_json, ok=rehearsal_ok if rehearsal_json.exists() else False)
    ready_stage_keys = {
        "package_manifest",
        "runbook",
        "zip",
        "recipes",
        "keithley_parameter_audits",
        "lockin_setting_audits",
    }
    ready_for_lab_review = all(stage["ok"] for stage in stages if stage["key"] in ready_stage_keys)
    return {
        "package_dir": str(package_dir),
        "package_manifest": str(manifest_path),
        "package_name": manifest.get("package_name"),
        "approved_next_scan": approved,
        "ready_for_lab_review": ready_for_lab_review,
        "stages": stages,
    }


def format_dual_gate_lockin_hall_suite_workflow_status(payload: dict) -> str:
    lines = [
        "Dual-gate lock-in Hall suite workflow status",
        f"Package: {payload.get('package_name') or 'n/a'}",
        f"Directory: {payload.get('package_dir')}",
        f"Ready for lab review: {payload.get('ready_for_lab_review')}",
        "",
        "| Stage | Status | Path | Details |",
        "| --- | --- | --- | --- |",
    ]
    for stage in payload.get("stages", []):
        status = "PASS" if stage.get("ok") else "MISSING" if not stage.get("exists") else "REVIEW"
        lines.append(
            f"| {stage.get('label')} | {status} | `{stage.get('path') or 'n/a'}` | {stage.get('details') or ''} |"
        )
    return "\n".join(lines)


def run_dual_gate_lockin_hall_suite_approved_next_scan_rehearsal(
    package_manifest_or_dir: Path,
    *,
    output_dir: Path | None,
    fake_gate1_leak_resistance_ohm: float,
    fake_gate2_leak_resistance_ohm: float,
    fake_lockin_r_v: float,
    fake_lockin_phase_deg: float,
    fake_noise_std_v: float,
    safety_dir: Path,
    overwrite: bool,
) -> dict:
    manifest_path = _resolve_package_manifest_path(package_manifest_or_dir)
    package_dir = manifest_path.parent
    manifest = _load_json_object(manifest_path)
    if "approved_next_scan" not in manifest:
        raise ValueError("package manifest is missing approved_next_scan provenance")
    out = output_dir or package_dir / "dry_run_rehearsal"
    if out.exists():
        if not overwrite:
            raise FileExistsError(f"Rehearsal output directory already exists: {out}")
        shutil.rmtree(out)
    out.mkdir(parents=True)
    rehearsal_manifest_path, recipe_paths = _prepare_rehearsal_package_manifest(manifest_path, manifest, package_dir, out)
    run_dir = out / "runs"
    run_dir.mkdir()
    run_dirs: dict[str, Path] = {}
    for key in ["longitudinal", "plus", "minus", "zero"]:
        if key not in recipe_paths:
            continue
        run_dirs[key] = _run_dual_gate_lockin_recipe_fake_for_rehearsal(
            recipe_paths[key],
            run_dir,
            safety_dir=safety_dir,
            fake_gate1_leak_resistance_ohm=fake_gate1_leak_resistance_ohm,
            fake_gate2_leak_resistance_ohm=fake_gate2_leak_resistance_ohm,
            fake_lockin_r_v=fake_lockin_r_v,
            fake_lockin_phase_deg=fake_lockin_phase_deg,
            fake_noise_std_v=fake_noise_std_v,
        )
    intake_json = out / "result_intake.json"
    intake_report = out / "result_intake_report.md"
    intake = write_dual_gate_lockin_hall_suite_result_intake(
        rehearsal_manifest_path,
        run_dirs["longitudinal"],
        run_dirs["plus"],
        run_dirs["minus"],
        zero_hall_run_dir=run_dirs.get("zero"),
        output_path=intake_report,
        json_output_path=intake_json,
        require_lockin_settings=False,
        overwrite=True,
    )
    if not intake.accepted:
        raise ValueError("dry-run rehearsal result intake did not pass")
    analysis = write_dual_gate_lockin_hall_suite_analysis(
        intake_json,
        output_dir=out / "hall_analysis",
        overwrite=True,
    )
    review = write_dual_gate_lockin_hall_suite_analysis_review(
        analysis.output_dir,
        overwrite=True,
    )
    if not review.accepted_for_next_scan_decision:
        raise ValueError("dry-run rehearsal analysis review did not pass")
    proposal = write_dual_gate_lockin_hall_suite_next_scan_proposal(
        analysis.output_dir,
        overwrite=True,
    )
    payload = {
        "package_manifest": str(manifest_path),
        "rehearsal_package_manifest": str(rehearsal_manifest_path),
        "output_dir": str(out),
        "runs": {key: str(path) for key, path in run_dirs.items()},
        "intake_json": str(intake_json),
        "analysis_dir": str(analysis.output_dir),
        "review_json": str(review.json_path),
        "next_proposal_json": str(proposal.json_path),
        "approved_next_scan": manifest.get("approved_next_scan"),
        "completed": True,
    }
    json_path = out / "rehearsal_summary.json"
    report_path = out / "rehearsal_report.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(_format_approved_next_scan_rehearsal_report(payload), encoding="utf-8")
    payload["json_path"] = str(json_path)
    payload["report_path"] = str(report_path)
    return payload


def _run_dual_gate_lockin_recipe_fake_for_rehearsal(
    recipe_path: Path,
    run_output_dir: Path,
    *,
    safety_dir: Path,
    fake_gate1_leak_resistance_ohm: float,
    fake_gate2_leak_resistance_ohm: float,
    fake_lockin_r_v: float,
    fake_lockin_phase_deg: float,
    fake_noise_std_v: float,
) -> Path:
    recipe = load_dual_gate_lockin_recipe(recipe_path)
    recipe = recipe.model_copy(update={"output": OutputConfig(directory=run_output_dir)})
    safety = load_named_safety_preset(recipe.safety_preset, safety_dir)
    gate1, gate2, lockin = _build_dual_gate_lockin_fake_instruments(
        fake_gate1_leak_resistance_ohm,
        fake_gate2_leak_resistance_ohm,
        fake_lockin_r_v,
        fake_lockin_phase_deg,
        fake_noise_std_v,
    )
    metadata = run_dual_gate_lockin_sweep(recipe, safety, gate1, gate2, lockin, recipe_path=recipe_path)
    if metadata.get("completed") is not True:
        raise ValueError(f"fake rehearsal run did not complete for {recipe_path}: {metadata.get('error_type')}")
    return Path(metadata["run_dir"])


def _build_dual_gate_lockin_fake_instruments(
    gate1_leak_resistance_ohm: float,
    gate2_leak_resistance_ohm: float,
    lockin_r_v: float,
    lockin_phase_deg: float,
    noise_std_v: float,
) -> tuple[DualGateFakeSMU, DualGateFakeSMU, DualGateFakeLockIn]:
    if gate1_leak_resistance_ohm <= 0:
        raise ValueError("--fake-gate1-leak-resistance-ohm must be > 0")
    if gate2_leak_resistance_ohm <= 0:
        raise ValueError("--fake-gate2-leak-resistance-ohm must be > 0")
    if lockin_r_v < 0:
        raise ValueError("--fake-lockin-r-v must be >= 0")
    if noise_std_v < 0:
        raise ValueError("--fake-noise-std-v must be >= 0")
    state = DualGateFakeDeviceState(
        gate1_leak_resistance_ohm=gate1_leak_resistance_ohm,
        gate2_leak_resistance_ohm=gate2_leak_resistance_ohm,
    )
    lockin = DualGateFakeLockIn(state, base_r_v=lockin_r_v, phase_deg=lockin_phase_deg, noise_std_v=noise_std_v)
    return DualGateFakeSMU("gate1", state), DualGateFakeSMU("gate2", state), lockin


def _prepare_rehearsal_package_manifest(
    source_manifest_path: Path,
    manifest: dict,
    package_dir: Path,
    output_dir: Path,
) -> tuple[Path, dict[str, Path]]:
    source_recipe_paths = _package_recipe_paths(manifest, package_dir)
    recipes_dir = output_dir / "recipes"
    recipes_dir.mkdir()
    copied: dict[str, Path] = {}
    for key, source_path in source_recipe_paths.items():
        target = recipes_dir / source_path.name
        data = yaml.safe_load(source_path.read_text(encoding="utf-8"))
        data["output"] = {**dict(data.get("output") or {}), "directory": str(output_dir / "runs")}
        target.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
        copied[key] = target
    rehearsal_manifest = dict(manifest)
    rehearsal_manifest["source_package_manifest"] = str(source_manifest_path)
    rehearsal_manifest["package_name"] = f"{manifest.get('package_name', 'package')}_dry_run_rehearsal"
    rehearsal_manifest["copied_recipes"] = {key: path.relative_to(output_dir).as_posix() for key, path in copied.items()}
    rehearsal_manifest["rehearsal"] = {
        "hardware_free": True,
        "source_package_dir": str(package_dir),
        "run_output_directory": str(output_dir / "runs"),
    }
    rehearsal_manifest_path = output_dir / "package_manifest.json"
    rehearsal_manifest_path.write_text(json.dumps(rehearsal_manifest, indent=2, sort_keys=True), encoding="utf-8")
    return rehearsal_manifest_path, copied


def _validate_manifest_path(
    value: object,
    package_dir: Path,
    checks: list[dict],
    issues: list[dict],
    *,
    key: str,
    label: str,
    code: str,
    required: bool,
) -> int:
    if not value:
        ok = not required
        checks.append({"key": key, "label": label, "ok": ok, "path": None, "details": "not present"})
        if required:
            issues.append({"severity": "error", "code": code, "message": f"{label} is missing from package manifest", "path": None})
        return 0
    path = Path(str(value))
    if not path.is_absolute():
        path = package_dir / path
    ok = path.exists()
    checks.append(
        {
            "key": key,
            "label": label,
            "ok": ok,
            "path": str(path),
            "details": "exists" if ok else "missing file",
        }
    )
    if not ok:
        issues.append({"severity": "error", "code": code, "message": f"{label} file does not exist", "path": str(path)})
    return 1 if ok else 0


def _validate_measurement_condition_audits(
    block: dict,
    package_dir: Path,
    checks: list[dict],
    issues: list[dict],
) -> None:
    schema_ok = block.get("schema_version") == 1
    checks.append(
        {
            "key": "measurement_condition_audits_schema",
            "label": "Measurement-condition audit schema",
            "ok": schema_ok,
            "path": None,
            "details": f"schema={block.get('schema_version')!r}",
        }
    )
    if not schema_ok:
        issues.append(
            {
                "severity": "error",
                "code": "unsupported_measurement_condition_audit_schema",
                "message": "measurement_condition_audits.schema_version should be 1",
                "path": None,
            }
        )
    records = block.get("records")
    records_ok = isinstance(records, list) and bool(records)
    checks.append(
        {
            "key": "measurement_condition_audits_records",
            "label": "Measurement-condition audit records",
            "ok": records_ok,
            "path": None,
            "details": f"{len(records) if isinstance(records, list) else 0} records",
        }
    )
    if not records_ok:
        issues.append(
            {
                "severity": "error",
                "code": "missing_measurement_condition_audit_records",
                "message": "measurement_condition_audits.records must be a non-empty list",
                "path": None,
            }
        )
        return
    instruments = {record.get("instrument") for record in records if isinstance(record, dict)}
    for instrument in ["keithley_2450", "srs_sr860"]:
        ok = instrument in instruments
        checks.append(
            {
                "key": f"measurement_condition_audits_{instrument}",
                "label": f"{instrument} audit records",
                "ok": ok,
                "path": None,
                "details": "present" if ok else "missing",
            }
        )
        if not ok:
            issues.append(
                {
                    "severity": "error",
                    "code": f"missing_{instrument}_audit_records",
                    "message": f"measurement_condition_audits.records is missing {instrument} entries",
                    "path": None,
                }
            )
    all_ok = bool(block.get("ok_for_hardware"))
    checks.append(
        {
            "key": "measurement_condition_audits_ok_for_hardware",
            "label": "Measurement-condition hardware readiness",
            "ok": all_ok,
            "path": None,
            "details": f"ok_for_hardware={block.get('ok_for_hardware')!r}",
        }
    )
    if not all_ok:
        issues.append(
            {
                "severity": "error",
                "code": "measurement_condition_audits_not_hardware_ready",
                "message": "measurement_condition_audits.ok_for_hardware must be true before lab handoff",
                "path": None,
            }
        )
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            issues.append(
                {
                    "severity": "error",
                    "code": "invalid_measurement_condition_audit_record",
                    "message": f"measurement_condition_audits.records[{index}] must be an object",
                    "path": None,
                }
            )
            continue
        label_prefix = f"{record.get('recipe_key', index)} {record.get('instrument', 'instrument')}"
        if not record.get("ok_for_hardware"):
            issues.append(
                {
                    "severity": "error",
                    "code": "audit_record_not_hardware_ready",
                    "message": f"{label_prefix} audit record is not hardware-ready",
                    "path": None,
                }
            )
        for field in ["json", "markdown"]:
            _validate_manifest_path(
                record.get(field),
                package_dir,
                checks,
                issues,
                key=f"audit_record_{index}_{field}",
                label=f"{label_prefix} {field} audit artifact",
                code=f"missing_audit_record_{field}",
                required=True,
            )


def _validate_legacy_audit_block(
    block: object,
    package_dir: Path,
    checks: list[dict],
    issues: list[dict],
    *,
    block_key: str,
    label: str,
    instrument: str,
) -> None:
    ok = isinstance(block, dict) and bool(block)
    checks.append({"key": block_key, "label": label, "ok": ok, "path": None, "details": "legacy fallback"})
    if not ok:
        issues.append(
            {
                "severity": "error",
                "code": f"missing_{block_key}",
                "message": f"package manifest is missing {label}",
                "path": None,
            }
        )
        return
    issues.append(
        {
            "severity": "warning",
            "code": f"legacy_{block_key}",
            "message": f"{label} is present only in legacy format; regenerate package to include measurement_condition_audits",
            "path": None,
        }
    )
    for recipe_key, record in block.items():
        if not isinstance(record, dict):
            issues.append(
                {
                    "severity": "error",
                    "code": "invalid_legacy_audit_record",
                    "message": f"{block_key}.{recipe_key} must be an object",
                    "path": None,
                }
            )
            continue
        if not record.get("ok_for_hardware"):
            issues.append(
                {
                    "severity": "error",
                    "code": "legacy_audit_not_hardware_ready",
                    "message": f"{instrument} legacy audit for {recipe_key} is not hardware-ready",
                    "path": None,
                }
            )
        for field in ["json", "markdown"]:
            _validate_manifest_path(
                record.get(field),
                package_dir,
                checks,
                issues,
                key=f"{block_key}_{recipe_key}_{field}",
                label=f"{instrument} {recipe_key} {field} audit artifact",
                code=f"missing_{block_key}_{field}",
                required=True,
            )


def _hall_suite_smoke_instrument_records(recipes: dict[str, object]) -> list[dict]:
    by_key: dict[tuple[str, str, str], dict] = {}
    for recipe_key, recipe in recipes.items():
        for role, instrument, address in [
            ("gate1", "keithley_2450", recipe.gate1_instrument.address),
            ("gate2", "keithley_2450", recipe.gate2_instrument.address),
            ("lockin", "srs_sr860", recipe.lockin.address),
        ]:
            key = (role, instrument, str(address))
            record = by_key.setdefault(
                key,
                {
                    "role": role,
                    "instrument": instrument,
                    "address": str(address),
                    "recipe_keys": [],
                },
            )
            record["recipe_keys"].append(recipe_key)
    return sorted(by_key.values(), key=lambda record: (record["instrument"], record["role"], record["address"]))


def _hall_suite_check_command(recipe_paths: dict[str, Path]) -> str:
    zero_arg = f" --zero-field-recipe {recipe_paths['zero']}" if "zero" in recipe_paths else ""
    return (
        f"ptm dual-gate-lockin-hall-suite-check {recipe_paths['longitudinal']} "
        f"{recipe_paths['plus']} {recipe_paths['minus']}{zero_arg}"
    )


def _hall_suite_plan_command(recipe_paths: dict[str, Path]) -> str:
    zero_arg = f" --zero-field-recipe {recipe_paths['zero']}" if "zero" in recipe_paths else ""
    return (
        f"ptm dual-gate-lockin-hall-suite-plan {recipe_paths['longitudinal']} "
        f"{recipe_paths['plus']} {recipe_paths['minus']}{zero_arg}"
    )


def _extract_active_dual_gate_lockin_commands(runbook_path: Path) -> list[str]:
    commands: list[str] = []
    for raw_line in runbook_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line.startswith("ptm dual-gate-lockin "):
            continue
        if "--allow-active-sweep" not in line:
            continue
        commands.append(line)
    return commands


def _command_flag_values(command: str) -> dict[str, str | bool]:
    tokens = command.split()
    flags: dict[str, str | bool] = {}
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token.startswith("--"):
            if index + 1 < len(tokens) and not tokens[index + 1].startswith("--"):
                flags[token] = tokens[index + 1].strip('"')
                index += 2
            else:
                flags[token] = True
                index += 1
        else:
            index += 1
    return flags


def _hardware_command_flag_check(
    command: str,
    flags: dict[str, str | bool],
    flag: str,
    *,
    required_value: object,
) -> dict:
    if flag not in flags:
        return {
            "flag": flag,
            "ok": False,
            "code": f"missing_{flag.lstrip('-').replace('-', '_')}",
            "message": f"missing required flag {flag}",
            "actual": None,
            "expected": required_value,
        }
    actual = flags[flag]
    if required_value is None:
        value_ok = bool(actual)
    else:
        value_ok = str(actual) == str(required_value)
    return {
        "flag": flag,
        "ok": value_ok,
        "code": f"invalid_{flag.lstrip('-').replace('-', '_')}",
        "message": f"{flag} expected {required_value!r} got {actual!r}",
        "actual": actual,
        "expected": required_value,
        "command": command,
    }


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resolve_package_manifest_path(package_manifest_or_dir: Path) -> Path:
    path = Path(package_manifest_or_dir)
    if path.is_dir():
        path = path / "package_manifest.json"
    if not path.exists():
        raise FileNotFoundError(f"Package manifest does not exist: {path}")
    return path


def _load_json_object(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _audit_record_paths(records: list[dict], package_dir: Path) -> list[Path]:
    paths: list[Path] = []
    for record in records:
        for field in ["json", "markdown"]:
            value = record.get(field)
            if value:
                path = Path(str(value))
                if not path.is_absolute():
                    path = package_dir / path
                paths.append(path)
    return paths


def _package_recipe_paths(manifest: dict, package_dir: Path) -> dict[str, Path]:
    copied = manifest.get("copied_recipes")
    if not isinstance(copied, dict):
        raise ValueError("package manifest is missing copied_recipes")
    paths = {}
    for key in ["longitudinal", "plus", "minus", "zero"]:
        value = copied.get(key)
        if not value:
            continue
        path = Path(str(value))
        if not path.is_absolute():
            path = package_dir / path
        if not path.exists():
            raise FileNotFoundError(f"Packaged {key} recipe does not exist: {path}")
        paths[key] = path
    for key in ["longitudinal", "plus", "minus"]:
        if key not in paths:
            raise ValueError(f"package manifest is missing copied recipe for {key}")
    return paths


def _format_approved_next_scan_rehearsal_report(payload: dict) -> str:
    return "\n".join(
        [
            "# Approved Next-Scan Package Dry-Run Rehearsal",
            "",
            f"- Package manifest: `{payload['package_manifest']}`",
            f"- Completed: {payload['completed']}",
            "",
            "## Fake Runs",
            "",
            *[f"- {key}: `{path}`" for key, path in payload["runs"].items()],
            "",
            "## Derived Artifacts",
            "",
            f"- Intake JSON: `{payload['intake_json']}`",
            f"- Analysis directory: `{payload['analysis_dir']}`",
            f"- Review JSON: `{payload['review_json']}`",
            f"- Next proposal JSON: `{payload['next_proposal_json']}`",
            "",
            "## Provenance Check",
            "",
            "- The input package contained `approved_next_scan` provenance.",
            "- The dry-run used copied package recipes with fake instruments.",
            "- Intake, Hall analysis, analysis review, and the next proposal all completed without hardware.",
            "",
        ]
    )
