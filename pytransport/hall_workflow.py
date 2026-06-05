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
from .hardware_evidence import (
    audit_hardware_evidence,
    format_hardware_evidence_audit,
    hardware_evidence_audit_to_dict,
)
from .instruments.fake import DualGateFakeDeviceState, DualGateFakeLockIn, DualGateFakeSMU
from .measurement_parameters import format_measurement_parameter_audit, measurement_parameter_audit_to_dict
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
    prerequisites = manifest.get("prerequisites")
    if isinstance(prerequisites, dict) and "four_terminal_ac_smoke_intake" in prerequisites:
        _validate_four_terminal_ac_smoke_prerequisite(
            prerequisites.get("four_terminal_ac_smoke_intake"),
            package_dir,
            checks,
            issues,
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
        "measurement_parameter_audit": [
            _hall_suite_measurement_parameter_audit_command(key, path, out)
            for key, path in recipe_paths.items()
        ],
        "measurement_parameter_audit_collect": [
            f"ptm dual-gate-lockin-hall-suite-lab-smoke-audits {package_dir} --overwrite"
        ],
        "post_run_intake": [
            _hall_suite_result_intake_command(package_dir, recipe_paths),
            f"ptm dual-gate-lockin-hall-suite-lab-return-manifest {package_dir} --operator-note \"<lab notebook reference>\" --overwrite",
        ],
    }
    prerequisite_summary = _four_terminal_ac_smoke_prerequisite_from_validation(validation)
    return_contract = _hall_suite_return_contract(recipe_paths)
    payload = {
        "package_dir": str(package_dir),
        "package_manifest": str(manifest_path),
        "package_name": manifest.get("package_name"),
        "output_dir": str(out),
        "safety_dir": str(safety_dir),
        "instrument_count": len(instruments),
        "instruments": instruments,
        "four_terminal_ac_smoke_prerequisite": prerequisite_summary,
        "recipe_paths": {key: str(path) for key, path in recipe_paths.items()},
        "return_contract": return_contract,
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
            "## Measurement Prerequisites",
            "",
            *_format_four_terminal_ac_smoke_prerequisite_summary(payload.get("four_terminal_ac_smoke_prerequisite") or {}),
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
            "## 6. Per-Recipe Measurement Parameter Audit",
            "",
            "```powershell",
            *commands.get("measurement_parameter_audit", []),
            "```",
            "",
            "Or collect all per-recipe audits at once:",
            "",
            "```powershell",
            *commands.get("measurement_parameter_audit_collect", []),
            "```",
            "",
            "## 7. Per-Recipe Preflight",
            "",
            "```powershell",
            *commands.get("preflight", []),
            "```",
            "",
            "## 8. Post-Run Intake And Return",
            "",
            *_format_hall_suite_return_contract(payload.get("return_contract") or {}),
            "",
            "```powershell",
            *commands.get("post_run_intake", []),
            "```",
            "",
            "## Pass Criteria",
            "",
            "- Package validation prints `Valid for lab handoff: True`.",
            "- Four-terminal AC prerequisite is PASS when attached.",
            "- `ptm list-resources` shows the two Keithley addresses and SR860 address.",
            "- Every Keithley identify response contains `MODEL 2450`.",
            "- SR860 identify response contains `SR860`.",
            "- Every probe completes without communication errors.",
            "- Every measurement-parameter audit reports `Hardware-ready: True` before preflight.",
            "- Every dual-gate lock-in preflight reports OK before any hardware output command is run.",
            "- After hardware runs, Hall-suite intake reports PASS before analysis.",
            "",
        ]
    )


def write_dual_gate_lockin_hall_suite_lab_smoke_parameter_audits(
    package_manifest_or_dir: Path,
    *,
    output_dir: Path | None = None,
    overwrite: bool = False,
) -> dict:
    validation = validate_dual_gate_lockin_hall_suite_package_manifest(package_manifest_or_dir)
    if not validation["valid"]:
        raise ValueError("package validation failed; run validate-package and fix issues before smoke audits")
    package_dir = Path(validation["package_dir"])
    manifest_path = Path(validation["package_manifest"])
    manifest = _load_json_object(manifest_path)
    recipe_paths = _package_recipe_paths(manifest, package_dir)
    out = output_dir or package_dir / "lab_smoke"
    out.mkdir(parents=True, exist_ok=True)
    summary_path = out / "measurement_parameter_audits.json"
    report_path = out / "measurement_parameter_audits.md"
    if (summary_path.exists() or report_path.exists()) and not overwrite:
        raise FileExistsError(f"Lab smoke measurement-parameter audit output already exists in {out}")

    records = []
    for recipe_key, recipe_path in recipe_paths.items():
        recipe = load_dual_gate_lockin_recipe(recipe_path)
        payload = {
            "recipe_key": recipe_key,
            "recipe_path": str(recipe_path),
            **measurement_parameter_audit_to_dict(recipe),
        }
        json_path = out / f"{recipe_key}_measurement_parameter_audit.json"
        markdown_path = out / f"{recipe_key}_measurement_parameter_audit.md"
        if (json_path.exists() or markdown_path.exists()) and not overwrite:
            raise FileExistsError(f"Lab smoke measurement-parameter audit already exists for {recipe_key}: {json_path}")
        json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        markdown_path.write_text(
            "\n".join(
                [
                    f"# {recipe_key} Measurement Parameter Audit",
                    "",
                    f"- Recipe: `{recipe_path}`",
                    f"- Hardware-ready: {payload['ok_for_hardware']}",
                    "",
                    format_measurement_parameter_audit(recipe),
                    "",
                ]
            ),
            encoding="utf-8",
        )
        records.append(
            {
                "recipe_key": recipe_key,
                "recipe_path": str(recipe_path),
                "json": str(json_path),
                "markdown": str(markdown_path),
                "ok_for_hardware": bool(payload["ok_for_hardware"]),
                "smu_ok_for_hardware": bool(payload["smu"]["ok_for_hardware"]),
                "lockin_ok_for_hardware": bool(payload["lockin"]["ok_for_hardware"]),
            }
        )

    summary = {
        "package_dir": str(package_dir),
        "package_manifest": str(manifest_path),
        "output_dir": str(out),
        "completed": True,
        "ok_for_hardware": all(record["ok_for_hardware"] for record in records),
        "record_count": len(records),
        "records": records,
    }
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(format_dual_gate_lockin_hall_suite_lab_smoke_parameter_audits(summary), encoding="utf-8")
    summary["json_path"] = str(summary_path)
    summary["report_path"] = str(report_path)
    return summary


def format_dual_gate_lockin_hall_suite_lab_smoke_parameter_audits(payload: dict) -> str:
    lines = [
        "# Hall Suite Lab Smoke Measurement Parameter Audits",
        "",
        f"- Package: `{payload.get('package_dir')}`",
        f"- Manifest: `{payload.get('package_manifest')}`",
        f"- Output dir: `{payload.get('output_dir')}`",
        f"- Hardware-ready: {payload.get('ok_for_hardware')}",
        "",
        "| Recipe | Status | SMU | SR860 | JSON | Markdown |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for record in payload.get("records", []):
        status = "PASS" if record.get("ok_for_hardware") else "REVIEW"
        smu_status = "PASS" if record.get("smu_ok_for_hardware") else "REVIEW"
        lockin_status = "PASS" if record.get("lockin_ok_for_hardware") else "REVIEW"
        lines.append(
            f"| {record.get('recipe_key')} | {status} | {smu_status} | {lockin_status} | "
            f"`{record.get('json')}` | `{record.get('markdown')}` |"
        )
    lines.extend(
        [
            "",
            "## Lab Use",
            "",
            "Continue to hardware preflight only when every row is PASS.",
            "",
        ]
    )
    return "\n".join(lines)


def _hall_suite_return_contract(recipe_paths: dict[str, Path]) -> dict:
    required_roles = ["longitudinal", "plus", "minus"]
    optional_roles = ["zero"] if "zero" in recipe_paths else []
    return {
        "required_run_roles": required_roles,
        "optional_run_roles": optional_roles,
        "expected_run_placeholders": {
            "longitudinal": "data\\raw\\<vxx_run>",
            "plus": "data\\raw\\<plus_B_run>",
            "minus": "data\\raw\\<minus_B_run>",
            **({"zero": "data\\raw\\<zero_B_run>"} if "zero" in recipe_paths else {}),
        },
        "required_post_run_artifacts": [
            "result_intake_report.md",
            "result_intake.json",
            "lab_return/lab_return_manifest.md",
            "lab_return/lab_return_manifest.json",
        ],
    }


def _format_hall_suite_return_contract(contract: dict) -> list[str]:
    placeholders = contract.get("expected_run_placeholders") if isinstance(contract.get("expected_run_placeholders"), dict) else {}
    lines = [
        "Returned run folders expected by role:",
        "",
        "| Role | Placeholder |",
        "| --- | --- |",
    ]
    for role in contract.get("required_run_roles") or []:
        lines.append(f"| {role} | `{placeholders.get(role) or 'n/a'}` |")
    for role in contract.get("optional_run_roles") or []:
        lines.append(f"| {role} | `{placeholders.get(role) or 'n/a'}` |")
    lines.extend(["", "Required post-run package artifacts:"])
    lines.extend(f"- `{artifact}`" for artifact in contract.get("required_post_run_artifacts") or [])
    return lines


def _hall_suite_result_intake_command(package_dir: Path, recipe_paths: dict[str, Path]) -> str:
    command = (
        f"ptm dual-gate-lockin-hall-suite-intake {package_dir} "
        "data\\raw\\<vxx_run> data\\raw\\<plus_B_run> data\\raw\\<minus_B_run>"
    )
    if "zero" in recipe_paths:
        command += " --zero-field-run-dir data\\raw\\<zero_B_run>"
    return command


def _hall_suite_measurement_parameter_audit_command(recipe_key: str, recipe_path: Path, output_dir: Path) -> str:
    json_path = output_dir / f"{recipe_key}_measurement_parameter_audit.json"
    return f"ptm measurement-parameter-audit dual_gate_lockin_sweep {recipe_path} --json-output {json_path}"


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
    lab_smoke_parameter_audits = write_dual_gate_lockin_hall_suite_lab_smoke_parameter_audits(
        package_dir,
        output_dir=out / "lab_smoke",
        overwrite=True,
    )
    hardware_review = review_dual_gate_lockin_hall_suite_hardware_commands(package_dir)
    package_validation_path = out / "package_validation.json"
    smoke_json_path = out / "lab_smoke_bundle.json"
    lab_smoke_parameter_audits_json_path = out / "lab_smoke_parameter_audits.json"
    hardware_review_path = out / "hardware_command_review.json"
    package_validation_path.write_text(json.dumps(validation, indent=2, sort_keys=True), encoding="utf-8")
    smoke_json_path.write_text(json.dumps(smoke, indent=2, sort_keys=True), encoding="utf-8")
    lab_smoke_parameter_audits_json_path.write_text(
        json.dumps(lab_smoke_parameter_audits, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    hardware_review_path.write_text(json.dumps(hardware_review, indent=2, sort_keys=True), encoding="utf-8")

    pass_state = (
        bool(validation.get("valid"))
        and bool(smoke.get("completed"))
        and bool(lab_smoke_parameter_audits.get("ok_for_hardware"))
        and bool(hardware_review.get("valid"))
    )
    prerequisite_summary = _four_terminal_ac_smoke_prerequisite_from_validation(validation)
    prerequisite_ok = prerequisite_summary["ok"] if prerequisite_summary["present"] else True
    pass_state = pass_state and prerequisite_ok
    payload = {
        "package_dir": str(package_dir),
        "package_manifest": validation.get("package_manifest"),
        "package_name": validation.get("package_name"),
        "output_dir": str(out),
        "pass": pass_state,
        "checks": {
            "package_validation": bool(validation.get("valid")),
            "four_terminal_ac_smoke_prerequisite": prerequisite_ok,
            "lab_smoke_bundle": bool(smoke.get("completed")),
            "lab_smoke_parameter_audits": bool(lab_smoke_parameter_audits.get("ok_for_hardware")),
            "hardware_command_review": bool(hardware_review.get("valid")),
        },
        "four_terminal_ac_smoke_prerequisite": prerequisite_summary,
        "lab_smoke_parameter_audits": {
            "ok": bool(lab_smoke_parameter_audits.get("ok_for_hardware")),
            "record_count": lab_smoke_parameter_audits.get("record_count"),
            "json": str(lab_smoke_parameter_audits_json_path),
            "source_json": lab_smoke_parameter_audits.get("json_path"),
            "source_markdown": lab_smoke_parameter_audits.get("report_path"),
        },
        "artifacts": {
            "package_validation_json": str(package_validation_path),
            "lab_smoke_bundle_json": str(smoke_json_path),
            "lab_smoke_checklist": smoke.get("report_path"),
            "lab_smoke_parameter_audits_json": str(lab_smoke_parameter_audits_json_path),
            "lab_smoke_parameter_audits_report": lab_smoke_parameter_audits.get("report_path"),
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
        f"| Four-terminal AC smoke prerequisite | {'PASS' if checks.get('four_terminal_ac_smoke_prerequisite') else 'REVIEW'} |",
        f"| Lab smoke bundle | {'PASS' if checks.get('lab_smoke_bundle') else 'REVIEW'} |",
        f"| Lab smoke measurement-parameter audits | {'PASS' if checks.get('lab_smoke_parameter_audits') else 'REVIEW'} |",
        f"| Hardware command review | {'PASS' if checks.get('hardware_command_review') else 'REVIEW'} |",
        "",
        "## Artifacts",
        "",
        f"- Package validation JSON: `{artifacts.get('package_validation_json')}`",
        f"- Lab smoke checklist: `{artifacts.get('lab_smoke_checklist')}`",
        f"- Lab smoke bundle JSON: `{artifacts.get('lab_smoke_bundle_json')}`",
        f"- Lab smoke measurement-parameter audit JSON: `{artifacts.get('lab_smoke_parameter_audits_json')}`",
        f"- Lab smoke measurement-parameter audit report: `{artifacts.get('lab_smoke_parameter_audits_report')}`",
        f"- Hardware command review JSON: `{artifacts.get('hardware_command_review_json')}`",
        "",
        "## Four-Terminal AC Prerequisite",
        "",
        *_format_four_terminal_ac_smoke_prerequisite_summary(payload.get("four_terminal_ac_smoke_prerequisite") or {}),
        "",
        "## Lab Use",
        "",
        "Attach this summary to the lab notebook entry for the package. Run the lab smoke checklist on the lab laptop before any active hardware command.",
        "",
    ]
    return "\n".join(lines)


def _four_terminal_ac_smoke_prerequisite_from_validation(validation: dict) -> dict:
    checks = {
        check.get("key"): check
        for check in validation.get("checks", [])
        if isinstance(check, dict)
    }
    present = "four_terminal_ac_smoke_prerequisite_record" in checks
    if not present:
        return {"present": False, "ok": True, "details": "not attached"}
    prerequisite_checks = [
        check
        for key, check in checks.items()
        if isinstance(key, str) and key.startswith("four_terminal_ac_smoke")
    ]
    ok = bool(prerequisite_checks) and all(bool(check.get("ok")) for check in prerequisite_checks)
    json_check = checks.get("four_terminal_ac_smoke_intake_json") or {}
    return {
        "present": True,
        "ok": ok,
        "details": "PASS" if ok else "REVIEW",
        "json_path": json_check.get("path"),
        "checks": prerequisite_checks,
    }


def _format_four_terminal_ac_smoke_prerequisite_summary(summary: dict) -> list[str]:
    if not summary.get("present"):
        return [
            "- Status: not attached",
            "- Recommendation: attach a PASS `ptm ac-lockin-lab-smoke-intake --json-output` artifact before graphene Hall-bar hardware scans.",
        ]
    lines = [
        f"- Status: {'PASS' if summary.get('ok') else 'REVIEW'}",
        f"- Intake JSON: `{summary.get('json_path') or 'n/a'}`",
    ]
    failed = [check for check in summary.get("checks", []) if not check.get("ok")]
    if failed:
        lines.append("- Failed checks:")
        lines.extend(f"  - {check.get('label')}: {check.get('details')}" for check in failed)
    return lines


def _four_terminal_ac_smoke_prerequisite_stage(manifest: dict, package_dir: Path) -> dict:
    prerequisites = manifest.get("prerequisites")
    record = prerequisites.get("four_terminal_ac_smoke_intake") if isinstance(prerequisites, dict) else None
    if not isinstance(record, dict):
        return {
            "path": package_dir / "prerequisites",
            "ok": False,
            "details": "not attached",
        }
    value = record.get("path")
    path = Path(str(value)) if value else package_dir / "prerequisites"
    if not path.is_absolute():
        path = package_dir / path
    contacts_ok = (
        isinstance(record.get("topology_excitation_contacts"), list)
        and isinstance(record.get("topology_lockin_input_contacts"), list)
        and len(record.get("topology_excitation_contacts")) == 2
        and len(record.get("topology_lockin_input_contacts")) == 2
        and not (set(record.get("topology_excitation_contacts")) & set(record.get("topology_lockin_input_contacts")))
    )
    ok = (
        path.exists()
        and record.get("accepted") is True
        and bool(str(record.get("hardware_guard_approval_note") or "").strip())
        and record.get("lockin_voltage_input") == "a-b"
        and record.get("source_nplc") is not None
        and contacts_ok
    )
    detail = "PASS" if ok else "REVIEW"
    if ok:
        detail = (
            f"PASS; NPLC={record.get('source_nplc')}, "
            f"contacts={record.get('topology_excitation_contacts')} -> {record.get('topology_lockin_input_contacts')}"
        )
    return {"path": path, "ok": ok, "details": detail}


def _lab_smoke_parameter_audits_stage(package_dir: Path) -> dict:
    candidates = [
        package_dir / "lab_smoke" / "measurement_parameter_audits.json",
        package_dir / "handoff_summary" / "lab_smoke" / "measurement_parameter_audits.json",
        package_dir / "handoff_summary" / "lab_smoke_parameter_audits.json",
    ]
    for path in candidates:
        if not path.exists():
            continue
        try:
            payload = _load_json_object(path)
        except ValueError:
            return {"path": path, "ok": False, "details": "invalid JSON"}
        records = payload.get("records")
        ok = (
            payload.get("completed") is True
            and payload.get("ok_for_hardware") is True
            and isinstance(records, list)
            and bool(records)
            and all(isinstance(record, dict) and bool(record.get("ok_for_hardware")) for record in records)
        )
        record_count = len(records) if isinstance(records, list) else 0
        return {
            "path": path,
            "ok": ok,
            "details": f"{record_count} recipe audits, ok_for_hardware={payload.get('ok_for_hardware')!r}",
        }
    return {
        "path": candidates[0],
        "ok": False,
        "details": "not written",
    }


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
    snapshot_json = package_dir / "condition_snapshot.json"
    snapshot_report = package_dir / "condition_snapshot_report.md"
    snapshot = _load_optional_json_object(snapshot_json)
    snapshot_runs = snapshot.get("runs") if isinstance(snapshot, dict) else None
    drift_json = package_dir / "condition_drift.json"
    drift_report = package_dir / "condition_drift_report.md"
    drift = _load_optional_json_object(drift_json)
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
        "condition_snapshot_json": str(snapshot_json) if snapshot_json.exists() else None,
        "condition_snapshot_report": str(snapshot_report) if snapshot_report.exists() else None,
        "condition_snapshot_run_count": len(snapshot_runs) if isinstance(snapshot_runs, list) else None,
        "condition_snapshot_written": bool(snapshot and isinstance(snapshot_runs, list) and bool(snapshot_runs)),
        "condition_drift_json": str(drift_json) if drift_json.exists() else None,
        "condition_drift_report": str(drift_report) if drift_report.exists() else None,
        "condition_drift_accepted": bool(drift and drift.get("accepted") is True),
        "condition_drift_issue_count": (
            len(drift.get("issues", [])) if isinstance(drift, dict) and isinstance(drift.get("issues"), list) else None
        ),
        "result_intake_accepted": bool(intake.get("accepted")),
        "result_intake_issue_count": len(intake.get("issues", [])) if isinstance(intake.get("issues"), list) else None,
        "runs": run_records,
        "operator_note": operator_note,
        "ready_for_analysis": bool(
            intake.get("accepted")
            and snapshot
            and isinstance(snapshot_runs, list)
            and bool(snapshot_runs)
            and drift
            and drift.get("accepted") is True
        ),
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
        f"- Condition snapshot: `{payload.get('condition_snapshot_report') or payload.get('condition_snapshot_json') or 'not written'}`",
        f"- Condition snapshot written: {payload.get('condition_snapshot_written')}",
        f"- Condition drift: `{payload.get('condition_drift_report') or payload.get('condition_drift_json') or 'not written'}`",
        f"- Condition drift accepted: {payload.get('condition_drift_accepted')}",
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


def write_dual_gate_lockin_hall_suite_hardware_evidence_audits(
    package_manifest_or_dir: Path,
    *,
    result_intake_json: Path | None = None,
    output_dir: Path | None = None,
    require_measurement_audit: bool = True,
    require_sr860_configure: bool = False,
    overwrite: bool = False,
) -> dict:
    manifest_path = _resolve_package_manifest_path(package_manifest_or_dir)
    package_dir = manifest_path.parent
    intake_path = result_intake_json or package_dir / "result_intake.json"
    intake = _load_json_object(intake_path)
    if intake.get("accepted") is not True:
        raise ValueError(f"{intake_path} is not accepted")
    runs = intake.get("runs")
    if not isinstance(runs, dict) or not runs:
        raise ValueError(f"{intake_path} is missing runs")
    out = output_dir or package_dir / "hardware_evidence_audits"
    if out.exists() and not overwrite:
        raise FileExistsError(f"Hall hardware evidence audits already exist: {out}")
    out.mkdir(parents=True, exist_ok=True)

    records: list[dict] = []
    for run_key, record in runs.items():
        run_dir_value = record.get("run_dir") if isinstance(record, dict) else None
        if not run_dir_value:
            records.append(
                {
                    "run_key": run_key,
                    "run_dir": None,
                    "accepted": False,
                    "json": None,
                    "markdown": None,
                    "issues": [
                        {
                            "check": "run_dir",
                            "severity": "error",
                            "message": "result_intake run record is missing run_dir",
                        }
                    ],
                }
            )
            continue
        run_dir = Path(str(run_dir_value))
        safe_key = _safe_artifact_name(str(run_key))
        json_path = out / f"{safe_key}_hardware_evidence_audit.json"
        report_path = out / f"{safe_key}_hardware_evidence_audit.md"
        try:
            audit = audit_hardware_evidence(
                run_dir,
                require_measurement_audit=require_measurement_audit,
                require_sr860_configure=require_sr860_configure,
            )
            audit_payload = hardware_evidence_audit_to_dict(audit)
            json_path.write_text(json.dumps(audit_payload, indent=2, sort_keys=True), encoding="utf-8")
            report_path.write_text(format_hardware_evidence_audit(audit), encoding="utf-8")
            records.append(
                {
                    "run_key": run_key,
                    "run_dir": str(run_dir),
                    "accepted": audit.accepted,
                    "json": str(json_path),
                    "markdown": str(report_path),
                    "issues": audit_payload.get("issues", []),
                    "measurement_type": audit.measurement_type,
                    "evidence_present": audit.evidence_present,
                }
            )
        except Exception as exc:
            records.append(
                {
                    "run_key": run_key,
                    "run_dir": str(run_dir),
                    "accepted": False,
                    "json": None,
                    "markdown": None,
                    "issues": [
                        {
                            "check": "hardware_evidence_audit",
                            "severity": "error",
                            "message": f"{type(exc).__name__}: {exc}",
                        }
                    ],
                }
            )

    accepted = bool(records) and all(record.get("accepted") is True for record in records)
    payload = {
        "schema": "pytransport.hall_suite_hardware_evidence_audits.v1",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "package_dir": str(package_dir),
        "package_manifest": str(manifest_path),
        "result_intake_json": str(intake_path),
        "accepted": accepted,
        "run_count": len(records),
        "require_measurement_audit": require_measurement_audit,
        "require_sr860_configure": require_sr860_configure,
        "records": records,
    }
    json_path = out / "hardware_evidence_audits.json"
    report_path = out / "hardware_evidence_audits.md"
    payload["json_path"] = str(json_path)
    payload["report_path"] = str(report_path)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(format_dual_gate_lockin_hall_suite_hardware_evidence_audits(payload), encoding="utf-8")
    return payload


def format_dual_gate_lockin_hall_suite_hardware_evidence_audits(payload: dict) -> str:
    lines = [
        "# Hall Suite Hardware Evidence Audits",
        "",
        f"- Package: `{payload.get('package_dir')}`",
        f"- Result intake: `{payload.get('result_intake_json')}`",
        f"- Accepted for analysis gate: {payload.get('accepted')}",
        f"- Require measurement-parameter audit evidence: {payload.get('require_measurement_audit')}",
        f"- Require SR860 configure evidence: {payload.get('require_sr860_configure')}",
        "",
        "| Run | Status | Run folder | Evidence present | Issues |",
        "| --- | --- | --- | --- | ---: |",
    ]
    for record in payload.get("records", []):
        issues = record.get("issues") if isinstance(record.get("issues"), list) else []
        lines.append(
            f"| {record.get('run_key')} | {'PASS' if record.get('accepted') else 'FAIL'} | "
            f"`{record.get('run_dir') or 'n/a'}` | {record.get('evidence_present')} | {len(issues)} |"
        )
    lines.extend(["", "## Audit Files", ""])
    for record in payload.get("records", []):
        lines.append(
            f"- {record.get('run_key')}: `{record.get('markdown') or record.get('json') or 'not written'}`"
        )
    lines.extend(
        [
            "",
            "## Lab Use",
            "",
            "Run this audit after result intake and before Hall analysis. It checks that returned hardware runs carry the measurement-parameter evidence used at execution time, including Keithley settings such as NPLC, ranges, and compliance.",
            "",
        ]
    )
    return "\n".join(lines)


def _hardware_evidence_audits_stage(package_dir: Path) -> dict:
    path = package_dir / "hardware_evidence_audits" / "hardware_evidence_audits.json"
    if not path.exists():
        return {"path": path, "ok": False, "details": "not written"}
    try:
        payload = _load_json_object(path)
    except ValueError:
        return {"path": path, "ok": False, "details": "invalid JSON"}
    records = payload.get("records")
    record_count = len(records) if isinstance(records, list) else 0
    ok = (
        payload.get("accepted") is True
        and isinstance(records, list)
        and bool(records)
        and all(isinstance(record, dict) and record.get("accepted") is True for record in records)
    )
    return {
        "path": path,
        "ok": ok,
        "details": f"{record_count} run audits, accepted={payload.get('accepted')!r}",
    }


def inspect_dual_gate_lockin_hall_suite_lifecycle_status(package_manifest_or_dir: Path) -> dict:
    workflow = inspect_dual_gate_lockin_hall_suite_workflow_status(package_manifest_or_dir)
    package_dir = Path(workflow["package_dir"])
    manifest_path = Path(workflow["package_manifest"])
    manifest = _load_json_object(manifest_path)
    workflow_stage_by_key = {stage.get("key"): stage for stage in workflow.get("stages", [])}
    stages: list[dict] = []

    def add_stage(key: str, label: str, path: Path, *, ok: bool, details: str = "") -> None:
        stages.append(
            {
                "key": key,
                "label": label,
                "path": str(path),
                "exists": path.exists(),
                "ok": bool(ok),
                "details": details,
            }
        )

    add_stage(
        "package_ready",
        "Package ready for lab review",
        manifest_path,
        ok=bool(workflow.get("ready_for_lab_review")),
        details="base package artifacts",
    )
    measurement_condition_audits = manifest.get("measurement_condition_audits")
    measurement_records = (
        measurement_condition_audits.get("records")
        if isinstance(measurement_condition_audits, dict)
        else None
    )
    add_stage(
        "measurement_condition_audits",
        "Measurement-condition audits",
        manifest_path,
        ok=bool(
            isinstance(measurement_condition_audits, dict)
            and measurement_condition_audits.get("ok_for_hardware") is True
            and isinstance(measurement_records, list)
            and bool(measurement_records)
        ),
        details=(
            f"{len(measurement_records)} records, ok_for_hardware={measurement_condition_audits.get('ok_for_hardware')!r}"
            if isinstance(measurement_records, list) and isinstance(measurement_condition_audits, dict)
            else "missing normalized measurement-condition audit block"
        ),
    )
    for key, label in [
        ("keithley_parameter_audits", "Keithley parameter audits"),
        ("lockin_setting_audits", "SR860 setting audits"),
    ]:
        workflow_stage = workflow_stage_by_key.get(key) or {}
        path_text = workflow_stage.get("path") or str(package_dir)
        add_stage(
            key,
            label,
            Path(path_text),
            ok=bool(workflow_stage.get("ok")),
            details=str(workflow_stage.get("details") or "not present"),
        )
    lab_smoke_parameter_stage = _lab_smoke_parameter_audits_stage(package_dir)
    add_stage(
        "lab_smoke_parameter_audits",
        "Lab smoke measurement-parameter audits",
        lab_smoke_parameter_stage["path"],
        ok=lab_smoke_parameter_stage["ok"],
        details=lab_smoke_parameter_stage["details"],
    )
    handoff_json = package_dir / "handoff_summary" / "handoff_summary.json"
    handoff = _load_optional_json_object(handoff_json)
    add_stage(
        "handoff_summary",
        "Lab handoff summary",
        handoff_json,
        ok=bool(handoff and handoff.get("pass") is True),
        details="ready for lab handoff" if handoff else "not written",
    )
    intake_json = package_dir / "result_intake.json"
    intake = _load_optional_json_object(intake_json)
    add_stage(
        "result_intake",
        "Result intake",
        intake_json,
        ok=bool(intake and intake.get("accepted") is True),
        details="accepted" if intake and intake.get("accepted") is True else "missing or not accepted",
    )
    hardware_evidence_stage = _hardware_evidence_audits_stage(package_dir)
    add_stage(
        "hardware_evidence_audits",
        "Hardware evidence audits",
        hardware_evidence_stage["path"],
        ok=hardware_evidence_stage["ok"],
        details=hardware_evidence_stage["details"],
    )
    snapshot_json = package_dir / "condition_snapshot.json"
    snapshot = _load_optional_json_object(snapshot_json)
    snapshot_runs = snapshot.get("runs") if isinstance(snapshot, dict) else None
    add_stage(
        "condition_snapshot",
        "Run condition snapshot",
        snapshot_json,
        ok=bool(snapshot and isinstance(snapshot_runs, list) and bool(snapshot_runs)),
        details=(
            f"{len(snapshot_runs)} runs"
            if isinstance(snapshot_runs, list) and snapshot_runs
            else "empty snapshot"
            if snapshot
            else "not written"
        ),
    )
    drift_json = package_dir / "condition_drift.json"
    drift = _load_optional_json_object(drift_json)
    add_stage(
        "condition_drift",
        "Acquisition-condition drift",
        drift_json,
        ok=bool(drift and drift.get("accepted") is True),
        details=(
            "no drift detected"
            if drift and drift.get("accepted") is True
            else f"{len(drift.get('issues') or [])} drift issues"
            if drift
            else "not written"
        ),
    )
    return_json = package_dir / "lab_return" / "lab_return_manifest.json"
    lab_return = _load_optional_json_object(return_json)
    add_stage(
        "lab_return",
        "Lab return manifest",
        return_json,
        ok=bool(lab_return and lab_return.get("ready_for_analysis") is True),
        details="ready for analysis" if lab_return else "not written",
    )
    analysis_json = package_dir / "hall_analysis" / "hall_suite_analysis_manifest.json"
    analysis = _load_optional_json_object(analysis_json)
    add_stage(
        "analysis",
        "Hall analysis",
        analysis_json,
        ok=analysis is not None,
        details="analysis artifacts written" if analysis else "not written",
    )
    review_json = package_dir / "hall_analysis" / "hall_suite_analysis_review.json"
    review = _load_optional_json_object(review_json)
    add_stage(
        "analysis_review",
        "Analysis review",
        review_json,
        ok=bool(review and review.get("accepted_for_next_scan_decision") is True),
        details="accepted for next-scan decision" if review else "not written",
    )
    proposal_json = package_dir / "hall_analysis" / "hall_suite_next_scan_proposal.json"
    proposal = _load_optional_json_object(proposal_json)
    add_stage(
        "next_scan_proposal",
        "Next-scan proposal",
        proposal_json,
        ok=proposal is not None,
        details=str(proposal.get("strategy") or "proposal written") if proposal else "not written",
    )
    return_bundle_json = package_dir / "return_bundle" / "return_bundle_index.json"
    return_bundle = _load_optional_json_object(return_bundle_json)
    missing_return_bundle_artifacts = (
        return_bundle.get("missing_artifact_count") if isinstance(return_bundle, dict) else None
    )
    add_stage(
        "return_bundle_index",
        "Return bundle index",
        return_bundle_json,
        ok=bool(return_bundle and missing_return_bundle_artifacts == 0),
        details=(
            f"missing_artifact_count={missing_return_bundle_artifacts}"
            if return_bundle
            else "not written"
        ),
    )
    state = _hall_suite_lifecycle_state(stages)
    measurement_conditions_ready = _lifecycle_measurement_conditions_ready(stages)
    return {
        "package_dir": str(package_dir),
        "package_manifest": workflow.get("package_manifest"),
        "package_name": workflow.get("package_name"),
        "state": state,
        "measurement_conditions_ready": measurement_conditions_ready,
        "lab_smoke_parameters_ready": _stage_ok(stages, "lab_smoke_parameter_audits"),
        "hardware_evidence_ready": _stage_ok(stages, "hardware_evidence_audits"),
        "ready_for_lab_handoff": (
            measurement_conditions_ready
            and _stage_ok(stages, "lab_smoke_parameter_audits")
            and _stage_ok(stages, "handoff_summary")
        ),
        "ready_for_analysis": (
            measurement_conditions_ready
            and _stage_ok(stages, "lab_smoke_parameter_audits")
            and _stage_ok(stages, "lab_return")
            and _stage_ok(stages, "result_intake")
            and _stage_ok(stages, "hardware_evidence_audits")
            and _stage_ok(stages, "condition_snapshot")
            and _stage_ok(stages, "condition_drift")
        ),
        "ready_for_next_scan_decision": (
            _stage_ok(stages, "condition_snapshot")
            and _stage_ok(stages, "condition_drift")
            and _stage_ok(stages, "analysis_review")
            and _stage_ok(stages, "next_scan_proposal")
        ),
        "return_bundle_archived": _stage_ok(stages, "return_bundle_index"),
        "stages": stages,
    }


def format_dual_gate_lockin_hall_suite_lifecycle_status(payload: dict) -> str:
    lines = [
        "Dual-gate lock-in Hall suite lifecycle status",
        f"Package: {payload.get('package_name') or 'n/a'}",
        f"Directory: {payload.get('package_dir')}",
        f"Lifecycle state: {payload.get('state')}",
        f"Measurement conditions ready: {payload.get('measurement_conditions_ready')}",
        f"Lab smoke parameters ready: {payload.get('lab_smoke_parameters_ready')}",
        f"Hardware evidence ready: {payload.get('hardware_evidence_ready')}",
        "",
        "| Stage | Status | Path | Details |",
        "| --- | --- | --- | --- |",
    ]
    for stage in payload.get("stages", []):
        if stage.get("ok"):
            status = "PASS"
        elif stage.get("exists"):
            status = "REVIEW"
        else:
            status = "MISSING"
        lines.append(f"| {stage.get('label')} | {status} | `{stage.get('path')}` | {stage.get('details') or ''} |")
    return "\n".join(lines)


def write_dual_gate_lockin_hall_suite_return_bundle_index(
    package_manifest_or_dir: Path,
    *,
    output_dir: Path | None = None,
    overwrite: bool = False,
) -> dict:
    lifecycle = inspect_dual_gate_lockin_hall_suite_lifecycle_status(package_manifest_or_dir)
    package_dir = Path(lifecycle["package_dir"])
    out = output_dir or package_dir / "return_bundle"
    if out.exists() and not overwrite:
        raise FileExistsError(f"Hall return bundle index already exists: {out}")
    out.mkdir(parents=True, exist_ok=True)
    artifacts = _hall_return_bundle_artifacts(package_dir, lifecycle)
    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "package_dir": str(package_dir),
        "package_manifest": lifecycle.get("package_manifest"),
        "package_name": lifecycle.get("package_name"),
        "lifecycle_state": lifecycle.get("state"),
        "ready_for_analysis": lifecycle.get("ready_for_analysis"),
        "ready_for_next_scan_decision": lifecycle.get("ready_for_next_scan_decision"),
        "artifact_count": len(artifacts),
        "missing_artifact_count": sum(1 for artifact in artifacts if not artifact["exists"]),
        "artifacts": artifacts,
    }
    json_path = out / "return_bundle_index.json"
    report_path = out / "return_bundle_index.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(format_dual_gate_lockin_hall_suite_return_bundle_index(payload), encoding="utf-8")
    payload["json_path"] = str(json_path)
    payload["report_path"] = str(report_path)
    return payload


def format_dual_gate_lockin_hall_suite_return_bundle_index(payload: dict) -> str:
    lines = [
        "# Hall Suite Return Bundle Index",
        "",
        f"- Package: `{payload.get('package_dir')}`",
        f"- Lifecycle state: {payload.get('lifecycle_state')}",
        f"- Ready for analysis: {payload.get('ready_for_analysis')}",
        f"- Ready for next-scan decision: {payload.get('ready_for_next_scan_decision')}",
        f"- Missing artifacts: {payload.get('missing_artifact_count')}/{payload.get('artifact_count')}",
        "",
        "| Artifact | Status | Path | Purpose |",
        "| --- | --- | --- | --- |",
    ]
    for artifact in payload.get("artifacts", []):
        status = "PRESENT" if artifact.get("exists") else "MISSING"
        lines.append(
            f"| {artifact.get('label')} | {status} | `{artifact.get('path')}` | {artifact.get('purpose')} |"
        )
    lines.extend(
        [
            "",
            "## Lab Use",
            "",
            "Attach this index to the lab notebook after returned runs are intaked. It is the table of contents for the returned Hall package.",
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
    prerequisite_stage = _four_terminal_ac_smoke_prerequisite_stage(manifest, package_dir)
    add_stage(
        "four_terminal_ac_smoke_prerequisite",
        "Four-terminal AC smoke prerequisite",
        prerequisite_stage["path"],
        ok=prerequisite_stage["ok"],
        details=prerequisite_stage["details"],
    )
    lab_smoke_parameter_stage = _lab_smoke_parameter_audits_stage(package_dir)
    add_stage(
        "lab_smoke_parameter_audits",
        "Lab smoke measurement-parameter audits",
        lab_smoke_parameter_stage["path"],
        ok=lab_smoke_parameter_stage["ok"],
        details=lab_smoke_parameter_stage["details"],
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


def _validate_four_terminal_ac_smoke_prerequisite(
    record: object,
    package_dir: Path,
    checks: list[dict],
    issues: list[dict],
) -> None:
    ok_record = isinstance(record, dict)
    checks.append(
        {
            "key": "four_terminal_ac_smoke_prerequisite_record",
            "label": "Four-terminal AC smoke prerequisite",
            "ok": ok_record,
            "path": None,
            "details": "present" if ok_record else "malformed",
        }
    )
    if not ok_record:
        issues.append(
            {
                "severity": "error",
                "code": "invalid_four_terminal_ac_smoke_prerequisite",
                "message": "prerequisites.four_terminal_ac_smoke_intake must be an object",
                "path": None,
            }
        )
        return
    _validate_manifest_path(
        record.get("path"),
        package_dir,
        checks,
        issues,
        key="four_terminal_ac_smoke_intake_json",
        label="Four-terminal AC smoke intake JSON",
        code="missing_four_terminal_ac_smoke_intake_json",
        required=True,
    )

    def add_field_check(key: str, label: str, ok: bool, details: str) -> None:
        checks.append({"key": key, "label": label, "ok": ok, "path": None, "details": details})
        if not ok:
            issues.append({"severity": "error", "code": key, "message": details, "path": None})

    excitation = record.get("topology_excitation_contacts")
    voltage = record.get("topology_lockin_input_contacts")
    add_field_check(
        "four_terminal_ac_smoke_accepted",
        "Four-terminal AC smoke accepted",
        record.get("accepted") is True,
        f"accepted={record.get('accepted')!r}",
    )
    add_field_check(
        "four_terminal_ac_smoke_guard_note",
        "Four-terminal AC guard approval note",
        bool(str(record.get("hardware_guard_approval_note") or "").strip()),
        "hardware_guard_approval_note present" if record.get("hardware_guard_approval_note") else "hardware_guard_approval_note missing",
    )
    add_field_check(
        "four_terminal_ac_smoke_voltage_input",
        "Four-terminal AC SR860 voltage input",
        record.get("lockin_voltage_input") == "a-b",
        f"lockin_voltage_input={record.get('lockin_voltage_input')!r}",
    )
    add_field_check(
        "four_terminal_ac_smoke_nplc",
        "Four-terminal AC Keithley NPLC",
        record.get("source_nplc") is not None,
        f"source_nplc={record.get('source_nplc')!r}",
    )
    add_field_check(
        "four_terminal_ac_smoke_contacts",
        "Four-terminal AC contact separation",
        isinstance(excitation, list)
        and isinstance(voltage, list)
        and len(excitation) == 2
        and len(voltage) == 2
        and not (set(excitation) & set(voltage)),
        f"excitation={excitation!r}, voltage={voltage!r}",
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


def _load_optional_json_object(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return _load_json_object(path)
    except ValueError:
        return None


def _hall_return_bundle_artifacts(package_dir: Path, lifecycle: dict) -> list[dict]:
    items = [
        ("Package manifest", package_dir / "package_manifest.json", "package contract and copied recipe index"),
        ("Acquisition runbook", package_dir / "acquisition_runbook.md", "lab-laptop acquisition commands"),
        ("Handoff summary", package_dir / "handoff_summary" / "handoff_summary.md", "pre-lab handoff PASS/REVIEW summary"),
        ("Result intake report", package_dir / "result_intake_report.md", "returned run acceptance report"),
        ("Result intake JSON", package_dir / "result_intake.json", "machine-readable returned run intake"),
        ("Condition snapshot report", package_dir / "condition_snapshot_report.md", "Vxx/+B/-B/0B measurement-condition table"),
        ("Condition snapshot JSON", package_dir / "condition_snapshot.json", "machine-readable condition snapshot"),
        ("Condition drift report", package_dir / "condition_drift_report.md", "returned-run measurement-condition drift audit"),
        ("Condition drift JSON", package_dir / "condition_drift.json", "machine-readable condition drift audit"),
        ("Lab return manifest", package_dir / "lab_return" / "lab_return_manifest.md", "returned package manifest for analysis handoff"),
        ("Lab return manifest JSON", package_dir / "lab_return" / "lab_return_manifest.json", "machine-readable lab return manifest"),
        ("Lifecycle status JSON", package_dir / "lifecycle_status.json", "optional saved lifecycle state"),
        ("Hall analysis report", package_dir / "hall_analysis" / "hall_suite_analysis_report.md", "analysis artifact index"),
        ("Hall analysis manifest", package_dir / "hall_analysis" / "hall_suite_analysis_manifest.json", "machine-readable analysis provenance"),
        ("Hall analysis review", package_dir / "hall_analysis" / "hall_suite_analysis_review.md", "next-scan readiness review"),
        ("Next-scan proposal", package_dir / "hall_analysis" / "hall_suite_next_scan_proposal.md", "advisory next gate scan proposal"),
    ]
    artifacts = [
        {
            "label": label,
            "path": str(path),
            "exists": path.exists(),
            "purpose": purpose,
        }
        for label, path, purpose in items
    ]
    for stage in lifecycle.get("stages", []):
        if stage.get("key") == "return_bundle_index":
            continue
        path = Path(str(stage.get("path"))) if stage.get("path") else package_dir
        artifacts.append(
            {
                "label": f"Lifecycle stage: {stage.get('label')}",
                "path": str(path),
                "exists": path.exists(),
                "ok": bool(stage.get("ok")),
                "purpose": f"stage status: {'PASS' if stage.get('ok') else 'REVIEW/MISSING'}; {stage.get('details') or ''}",
            }
        )
    return artifacts


def _stage_ok(stages: list[dict], key: str) -> bool:
    return any(stage.get("key") == key and stage.get("ok") is True for stage in stages)


def _lifecycle_measurement_conditions_ready(stages: list[dict]) -> bool:
    return (
        _stage_ok(stages, "measurement_condition_audits")
        and _stage_ok(stages, "keithley_parameter_audits")
        and _stage_ok(stages, "lockin_setting_audits")
    )


def _hall_suite_lifecycle_state(stages: list[dict]) -> str:
    measurement_conditions_ready = _lifecycle_measurement_conditions_ready(stages)
    if _stage_ok(stages, "return_bundle_index"):
        return "return_bundle_archived"
    if not measurement_conditions_ready:
        if (
            _stage_ok(stages, "handoff_summary")
            or _stage_ok(stages, "result_intake")
            or _stage_ok(stages, "lab_return")
            or _stage_ok(stages, "analysis")
        ):
            return "measurement_condition_review"
    if (
        measurement_conditions_ready
        and (
            _stage_ok(stages, "handoff_summary")
            or _stage_ok(stages, "result_intake")
            or _stage_ok(stages, "lab_return")
            or _stage_ok(stages, "analysis")
        )
        and not _stage_ok(stages, "lab_smoke_parameter_audits")
    ):
        return "lab_smoke_parameter_review"
    if _stage_ok(stages, "result_intake") and not _stage_ok(stages, "hardware_evidence_audits"):
        evidence_stage = next((stage for stage in stages if stage.get("key") == "hardware_evidence_audits"), {})
        if evidence_stage.get("exists"):
            return "hardware_evidence_review"
        return "hardware_evidence_pending"
    if _stage_ok(stages, "result_intake") and not _stage_ok(stages, "condition_snapshot"):
        snapshot_stage = next((stage for stage in stages if stage.get("key") == "condition_snapshot"), {})
        if snapshot_stage.get("exists"):
            return "condition_snapshot_review"
        return "condition_snapshot_pending"
    if _stage_ok(stages, "result_intake") and not _stage_ok(stages, "condition_drift"):
        drift_stage = next((stage for stage in stages if stage.get("key") == "condition_drift"), {})
        if drift_stage.get("exists"):
            return "acquisition_condition_drift"
        return "condition_drift_pending"
    if _stage_ok(stages, "next_scan_proposal"):
        return "next_scan_proposed"
    if _stage_ok(stages, "analysis_review"):
        return "analysis_reviewed"
    if _stage_ok(stages, "analysis"):
        return "analysis_written"
    if (
        measurement_conditions_ready
        and _stage_ok(stages, "lab_return")
        and _stage_ok(stages, "result_intake")
        and _stage_ok(stages, "hardware_evidence_audits")
        and _stage_ok(stages, "condition_snapshot")
        and _stage_ok(stages, "condition_drift")
    ):
        return "ready_for_analysis"
    if _stage_ok(stages, "result_intake"):
        return "intake_accepted"
    if (
        measurement_conditions_ready
        and _stage_ok(stages, "lab_smoke_parameter_audits")
        and _stage_ok(stages, "handoff_summary")
    ):
        return "ready_for_lab_handoff"
    if _stage_ok(stages, "package_ready"):
        return "package_ready"
    return "package_incomplete"


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


def _safe_artifact_name(value: str) -> str:
    return "".join(char if char.isalnum() or char in "._-" else "_" for char in value).strip("._") or "artifact"


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
