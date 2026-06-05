"""Hall-suite workflow orchestration helpers.

These helpers keep hardware-free rehearsal and read-only workflow status logic
outside the CLI so GUI/API layers can reuse the same core behavior.
"""

from __future__ import annotations

import json
import shutil
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
    keithley_audits = manifest.get("keithley_parameter_audits")
    audit_paths: list[Path] = []
    audit_ok = False
    audit_details = "not present"
    if isinstance(keithley_audits, dict):
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
    if isinstance(lockin_audits, dict):
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
