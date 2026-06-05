"""Post-run audit for hardware evidence provenance."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from .inspect import read_run_metadata
from .measurement_parameters import check_measurement_parameter_audit_evidence_file
from .method_registry import handler_for_measurement_type, measurement_type_from_metadata
from .sr860_config import check_sr860_configure_evidence, load_sr860_configure_json


@dataclass(frozen=True)
class HardwareEvidenceIssue:
    check: str
    severity: str
    message: str


@dataclass(frozen=True)
class HardwareEvidenceAudit:
    run_dir: Path
    metadata_path: Path
    measurement_type: str
    evidence_present: bool
    accepted: bool
    issues: tuple[HardwareEvidenceIssue, ...]
    evidence: dict[str, Any] | None
    measurement_audit_check: dict[str, Any] | None
    sr860_configure_check: dict[str, Any] | None


def audit_hardware_evidence(
    run_dir: str | Path,
    *,
    require_measurement_audit: bool = False,
    require_sr860_configure: bool = False,
) -> HardwareEvidenceAudit:
    path = Path(run_dir)
    metadata_path = path / "metadata.json"
    metadata = read_run_metadata(path)
    measurement_type = measurement_type_from_metadata(metadata)
    evidence = metadata.get("hardware_evidence")
    issues: list[HardwareEvidenceIssue] = []
    measurement_check = None
    sr860_check = None

    if not isinstance(evidence, dict):
        severity = "error" if require_measurement_audit or require_sr860_configure else "warning"
        issues.append(HardwareEvidenceIssue("hardware_evidence_present", severity, "metadata.hardware_evidence is missing"))
        return HardwareEvidenceAudit(
            run_dir=path,
            metadata_path=metadata_path,
            measurement_type=measurement_type,
            evidence_present=False,
            accepted=not any(issue.severity == "error" for issue in issues),
            issues=tuple(issues),
            evidence=None,
            measurement_audit_check=None,
            sr860_configure_check=None,
        )

    if evidence.get("schema") != "pytransport.hardware_evidence.v1":
        issues.append(
            HardwareEvidenceIssue(
                "hardware_evidence_schema",
                "error",
                f"unexpected hardware_evidence.schema={evidence.get('schema')!r}",
            )
        )

    if evidence.get("preflight_reran_after_evidence_check") is not True:
        issues.append(
            HardwareEvidenceIssue(
                "preflight_reran_after_evidence_check",
                "error",
                "hardware_evidence.preflight_reran_after_evidence_check must be true",
            )
        )

    recipe_path = _metadata_recipe_path(metadata)
    measurement_audit_json = evidence.get("measurement_audit_json")
    if measurement_audit_json:
        if evidence.get("measurement_audit_evidence_passed") is not True:
            issues.append(
                HardwareEvidenceIssue(
                    "measurement_audit_evidence_passed",
                    "error",
                    "metadata says measurement audit evidence did not pass",
                )
            )
        measurement_check = _check_measurement_audit_file(
            measurement_type,
            recipe_path,
            measurement_audit_json,
            issues,
        )
    elif require_measurement_audit:
        issues.append(
            HardwareEvidenceIssue(
                "measurement_audit_json",
                "error",
                "hardware_evidence.measurement_audit_json is required but missing",
            )
        )

    sr860_configure_json = evidence.get("sr860_configure_json")
    if sr860_configure_json:
        if evidence.get("sr860_configure_evidence_passed") is not True:
            issues.append(
                HardwareEvidenceIssue(
                    "sr860_configure_evidence_passed",
                    "error",
                    "metadata says SR860 configure evidence did not pass",
                )
            )
        sr860_check = _check_sr860_configure_file(measurement_type, recipe_path, sr860_configure_json, issues)
    elif require_sr860_configure:
        issues.append(
            HardwareEvidenceIssue(
                "sr860_configure_json",
                "error",
                "hardware_evidence.sr860_configure_json is required but missing",
            )
        )

    accepted = not any(issue.severity == "error" for issue in issues)
    return HardwareEvidenceAudit(
        run_dir=path,
        metadata_path=metadata_path,
        measurement_type=measurement_type,
        evidence_present=True,
        accepted=accepted,
        issues=tuple(issues),
        evidence=evidence,
        measurement_audit_check=measurement_check,
        sr860_configure_check=sr860_check,
    )


def hardware_evidence_audit_to_dict(audit: HardwareEvidenceAudit) -> dict[str, Any]:
    return {
        "schema": "pytransport.hardware_evidence_audit.v1",
        "run_dir": str(audit.run_dir),
        "metadata_path": str(audit.metadata_path),
        "measurement_type": audit.measurement_type,
        "evidence_present": audit.evidence_present,
        "accepted": audit.accepted,
        "issues": [
            {"check": issue.check, "severity": issue.severity, "message": issue.message}
            for issue in audit.issues
        ],
        "hardware_evidence": audit.evidence,
        "measurement_audit_check": audit.measurement_audit_check,
        "sr860_configure_check": audit.sr860_configure_check,
    }


def format_hardware_evidence_audit(audit: HardwareEvidenceAudit) -> str:
    evidence = audit.evidence or {}
    lines = [
        f"Hardware evidence audit: {'PASS' if audit.accepted else 'FAIL'}",
        f"Run: {audit.run_dir}",
        f"Metadata: {audit.metadata_path}",
        f"Measurement type: {audit.measurement_type}",
        f"Evidence present: {audit.evidence_present}",
        f"Measurement audit JSON: {evidence.get('measurement_audit_json') or 'n/a'}",
        f"Measurement audit evidence passed: {evidence.get('measurement_audit_evidence_passed')}",
        f"SR860 configure JSON: {evidence.get('sr860_configure_json') or 'n/a'}",
        f"SR860 configure evidence passed: {evidence.get('sr860_configure_evidence_passed')}",
        f"Preflight reran after evidence check: {evidence.get('preflight_reran_after_evidence_check')}",
    ]
    if audit.measurement_audit_check is not None:
        lines.append(f"Measurement audit recheck: {audit.measurement_audit_check.get('ok')}")
    if audit.sr860_configure_check is not None:
        lines.append(f"SR860 configure recheck: {audit.sr860_configure_check.get('ok')}")
    if audit.issues:
        lines.append("")
        lines.append("Issues")
        for issue in audit.issues:
            lines.append(f"- {issue.severity.upper()} {issue.check}: {issue.message}")
    return "\n".join(lines)


def write_hardware_evidence_audit_json(audit: HardwareEvidenceAudit, output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(hardware_evidence_audit_to_dict(audit), indent=2, sort_keys=True), encoding="utf-8")
    return path


def _metadata_recipe_path(metadata: dict[str, Any]) -> Path | None:
    recipe_path = metadata.get("recipe_path")
    if not recipe_path:
        return None
    return Path(str(recipe_path))


def _check_measurement_audit_file(
    measurement_type: str,
    recipe_path: Path | None,
    audit_json: Any,
    issues: list[HardwareEvidenceIssue],
) -> dict[str, Any] | None:
    audit_path = Path(str(audit_json))
    if not audit_path.exists():
        issues.append(HardwareEvidenceIssue("measurement_audit_json_exists", "error", f"missing file: {audit_path}"))
        return None
    if recipe_path is None or not recipe_path.exists():
        issues.append(
            HardwareEvidenceIssue(
                "measurement_audit_recheck",
                "warning",
                "recipe_path is missing or unavailable, so saved measurement audit could not be recomputed",
            )
        )
        return None
    recipe = handler_for_measurement_type(measurement_type).load_recipe(recipe_path)
    payload = check_measurement_parameter_audit_evidence_file(measurement_type, recipe_path, recipe, audit_path)
    if not payload.get("ok"):
        issues.append(
            HardwareEvidenceIssue(
                "measurement_audit_recheck",
                "error",
                "saved measurement audit no longer matches recipe_path",
            )
        )
    return payload


def _check_sr860_configure_file(
    measurement_type: str,
    recipe_path: Path | None,
    configure_json: Any,
    issues: list[HardwareEvidenceIssue],
) -> dict[str, Any] | None:
    configure_path = Path(str(configure_json))
    if not configure_path.exists():
        issues.append(HardwareEvidenceIssue("sr860_configure_json_exists", "error", f"missing file: {configure_path}"))
        return None
    if recipe_path is None or not recipe_path.exists():
        issues.append(
            HardwareEvidenceIssue(
                "sr860_configure_recheck",
                "warning",
                "recipe_path is missing or unavailable, so saved SR860 configure evidence could not be recomputed",
            )
        )
        return None
    recipe = handler_for_measurement_type(measurement_type).load_recipe(recipe_path)
    payload = check_sr860_configure_evidence(recipe, load_sr860_configure_json(configure_path))
    if not payload.get("ok"):
        issues.append(
            HardwareEvidenceIssue(
                "sr860_configure_recheck",
                "error",
                "saved SR860 configure transcript no longer matches recipe_path",
            )
        )
    return {"path": str(configure_path), **payload}
