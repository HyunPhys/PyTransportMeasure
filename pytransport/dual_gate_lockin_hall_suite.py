"""Template helpers for a Hall-bar dual-gate lock-in measurement suite."""

from __future__ import annotations

import csv
import json
import shutil
from dataclasses import dataclass
from datetime import datetime
from math import isfinite
from pathlib import Path
from typing import Any

import yaml

from .dual_gate_lockin import (
    dual_gate_lockin_grid_signature,
    dual_gate_lockin_point_count,
    format_dual_gate_lockin_plan,
)
from .dual_gate_lockin_review import (
    audit_dual_gate_lockin_run,
    format_dual_gate_lockin_acceptance,
    read_dual_gate_lockin_metadata,
)
from .dual_gate_lockin_scaleup import build_dual_gate_lockin_adjusted_recipe_data
from .hall_analysis import (
    HALL_ANTISYM_COLUMNS,
    HALL_MOBILITY_COLUMNS,
    HALL_ZERO_CORRECTED_COLUMNS,
    HallValueColumn,
    write_dual_gate_lockin_hall_antisym,
    write_dual_gate_lockin_hall_mobility,
    write_dual_gate_lockin_hall_zero_corrected,
)
from .measurement_parameters import (
    audit_lockin_hardware_parameters,
    audit_smu_hardware_parameters,
    format_smu_hardware_parameter_audit,
    lockin_hardware_parameter_audit_to_dict,
    smu_hardware_parameter_audit_to_dict,
)
from .lockin_settings import expected_lockin_settings
from .lockin_timing import lockin_read_settle_s, lockin_time_constant_s
from .recipes import DualGateLockInRecipe, SafetyPreset, load_named_safety_preset, load_yaml


@dataclass(frozen=True)
class HallSuiteTemplateResult:
    output_dir: Path
    longitudinal_recipe: Path
    plus_hall_recipe: Path
    minus_hall_recipe: Path
    zero_hall_recipe: Path | None
    review_path: Path


@dataclass(frozen=True)
class HallSuiteIssue:
    severity: str
    check: str
    message: str


@dataclass(frozen=True)
class HallSuiteAudit:
    longitudinal_recipe: Path
    plus_hall_recipe: Path
    minus_hall_recipe: Path
    zero_hall_recipe: Path | None
    compatible: bool
    point_count: int | None
    issues: tuple[HallSuiteIssue, ...]


@dataclass(frozen=True)
class HallSuiteAdjustmentResult:
    output_dir: Path
    longitudinal_recipe: Path
    plus_hall_recipe: Path
    minus_hall_recipe: Path
    zero_hall_recipe: Path | None
    review_path: Path


@dataclass(frozen=True)
class HallSuiteAcquisitionPackageResult:
    package_dir: Path
    recipes_dir: Path
    runbook_path: Path
    manifest_path: Path
    zip_path: Path


@dataclass(frozen=True)
class HallSuiteResultIntakeIssue:
    severity: str
    check: str
    message: str


@dataclass(frozen=True)
class HallSuiteResultIntake:
    package_manifest_path: Path
    accepted: bool
    report_path: Path | None
    json_path: Path | None
    issues: tuple[HallSuiteResultIntakeIssue, ...]


@dataclass(frozen=True)
class HallSuiteConditionDriftIssue:
    severity: str
    run_key: str
    field: str
    expected: Any
    actual: Any
    message: str


@dataclass(frozen=True)
class HallSuiteConditionDriftAudit:
    package_manifest_path: Path
    result_intake_json_path: Path
    accepted: bool
    report_path: Path | None
    json_path: Path | None
    issues: tuple[HallSuiteConditionDriftIssue, ...]


@dataclass(frozen=True)
class HallSuiteConditionSnapshotReport:
    package_manifest_path: Path
    result_intake_json_path: Path
    report_path: Path
    json_path: Path
    run_count: int


@dataclass(frozen=True)
class HallSuiteAnalysisResult:
    output_dir: Path
    antisym_dir: Path
    zero_corrected_dir: Path | None
    mobility_dir: Path
    report_path: Path
    manifest_path: Path


@dataclass(frozen=True)
class HallSuiteAnalysisReviewIssue:
    severity: str
    check: str
    message: str


@dataclass(frozen=True)
class HallSuiteAnalysisReview:
    analysis_dir: Path
    accepted_for_next_scan_decision: bool
    report_path: Path
    json_path: Path
    issues: tuple[HallSuiteAnalysisReviewIssue, ...]


@dataclass(frozen=True)
class HallSuiteNextScanProposal:
    review_json_path: Path
    accepted_for_recipe_generation: bool
    report_path: Path
    json_path: Path


@dataclass(frozen=True)
class HallSuiteApprovedNextScanResult:
    output_dir: Path
    longitudinal_recipe: Path
    plus_hall_recipe: Path
    minus_hall_recipe: Path
    zero_hall_recipe: Path | None
    review_path: Path


def write_dual_gate_lockin_hall_suite_template(
    base_recipe_path: str | Path,
    output_dir: str | Path,
    *,
    measurement_prefix: str | None = None,
    magnetic_field_t: float,
    longitudinal_contacts: list[str] | None = None,
    hall_contacts: list[str] | None = None,
    channel_length_m: float | None = None,
    channel_width_m: float | None = None,
    include_zero_field: bool = True,
    run_output_directory: str | Path | None = None,
    safety_dir: str | Path = "configs/safety",
    overwrite: bool = False,
) -> HallSuiteTemplateResult:
    base_path = Path(base_recipe_path)
    base_data = load_yaml(base_path)
    base_recipe = DualGateLockInRecipe.model_validate(base_data)
    if magnetic_field_t <= 0:
        raise ValueError("magnetic_field_t must be positive; plus/minus recipes set the sign")

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    prefix = measurement_prefix or f"{base_recipe.measurement_name}_hall_suite"
    longitudinal_data = _recipe_variant(
        base_data,
        measurement_name=f"{prefix}_vxx",
        voltage_probe_role="longitudinal",
        magnetic_field_t=None,
        lockin_input_contacts=longitudinal_contacts,
        channel_length_m=channel_length_m,
        channel_width_m=channel_width_m,
        run_output_directory=run_output_directory,
    )
    plus_data = _recipe_variant(
        base_data,
        measurement_name=f"{prefix}_vxy_plus_b",
        voltage_probe_role="hall",
        magnetic_field_t=magnetic_field_t,
        lockin_input_contacts=hall_contacts,
        channel_length_m=None,
        channel_width_m=None,
        run_output_directory=run_output_directory,
    )
    minus_data = _recipe_variant(
        base_data,
        measurement_name=f"{prefix}_vxy_minus_b",
        voltage_probe_role="hall",
        magnetic_field_t=-magnetic_field_t,
        lockin_input_contacts=hall_contacts,
        channel_length_m=None,
        channel_width_m=None,
        run_output_directory=run_output_directory,
    )
    zero_data = (
        _recipe_variant(
            base_data,
            measurement_name=f"{prefix}_vxy_zero_b",
            voltage_probe_role="hall",
            magnetic_field_t=0.0,
            lockin_input_contacts=hall_contacts,
            channel_length_m=None,
            channel_width_m=None,
            run_output_directory=run_output_directory,
        )
        if include_zero_field
        else None
    )

    longitudinal_path = out / f"{prefix}_vxx.yaml"
    plus_path = out / f"{prefix}_vxy_plus_b.yaml"
    minus_path = out / f"{prefix}_vxy_minus_b.yaml"
    zero_path = out / f"{prefix}_vxy_zero_b.yaml" if zero_data is not None else None
    _write_recipe(longitudinal_path, longitudinal_data, overwrite=overwrite)
    _write_recipe(plus_path, plus_data, overwrite=overwrite)
    _write_recipe(minus_path, minus_data, overwrite=overwrite)
    if zero_path is not None and zero_data is not None:
        _write_recipe(zero_path, zero_data, overwrite=overwrite)

    review_path = out / f"{prefix}_review.md"
    if review_path.exists() and not overwrite:
        raise FileExistsError(f"Review file already exists: {review_path}")
    safety = load_named_safety_preset(base_recipe.safety_preset, safety_dir)
    review_path.write_text(
        format_hall_suite_review(
            base_path,
            longitudinal_path,
            plus_path,
            minus_path,
            zero_path,
            longitudinal_data,
            plus_data,
            safety,
        ),
        encoding="utf-8",
    )
    return HallSuiteTemplateResult(out, longitudinal_path, plus_path, minus_path, zero_path, review_path)


def write_dual_gate_lockin_hall_suite_adjusted_recipes(
    longitudinal_recipe: str | Path,
    plus_hall_recipe: str | Path,
    minus_hall_recipe: str | Path,
    output_dir: str | Path,
    *,
    zero_hall_recipe: str | Path | None = None,
    measurement_prefix: str | None = None,
    run_output_directory: str | Path | None = None,
    gate1_nplc: float | None = None,
    gate2_nplc: float | None = None,
    gate_nplc: float | None = None,
    gate1_settle_s: float | None = None,
    gate2_settle_s: float | None = None,
    gate_settle_s: float | None = None,
    lockin_sensitivity_index: int | None = None,
    lockin_time_constant_index: int | None = None,
    lockin_settle_time_constants: float | None = None,
    lockin_read_settle_s: float | None = None,
    adjustment_note: str | None = None,
    safety_dir: str | Path = "configs/safety",
    overwrite: bool = False,
) -> HallSuiteAdjustmentResult:
    input_audit = audit_dual_gate_lockin_hall_suite(
        longitudinal_recipe,
        plus_hall_recipe,
        minus_hall_recipe,
        zero_hall_recipe=zero_hall_recipe,
    )
    if not input_audit.compatible:
        raise ValueError("input Hall suite is not compatible; run dual-gate-lockin-hall-suite-check first")

    input_recipes = _load_suite_recipes(input_audit)
    prefix = measurement_prefix or f"{input_recipes['longitudinal'].measurement_name}_adjusted_suite"
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    output_paths: dict[str, Path] = {}
    for key, _, input_path, recipe in _suite_key_entries(input_audit, input_recipes):
        measurement_name = _suite_adjusted_measurement_name(prefix, recipe)
        output_path = out / f"{measurement_name}.yaml"
        data = build_dual_gate_lockin_adjusted_recipe_data(
            input_path,
            measurement_name=measurement_name,
            output_directory=run_output_directory,
            gate1_nplc=gate1_nplc,
            gate2_nplc=gate2_nplc,
            gate_nplc=gate_nplc,
            gate1_settle_s=gate1_settle_s,
            gate2_settle_s=gate2_settle_s,
            gate_settle_s=gate_settle_s,
            lockin_sensitivity_index=lockin_sensitivity_index,
            lockin_time_constant_index=lockin_time_constant_index,
            lockin_settle_time_constants=lockin_settle_time_constants,
            lockin_read_settle_s=lockin_read_settle_s,
            adjustment_note=adjustment_note,
        )
        _write_recipe(output_path, data, overwrite=overwrite)
        output_paths[key] = output_path

    output_audit = audit_dual_gate_lockin_hall_suite(
        output_paths["longitudinal"],
        output_paths["plus"],
        output_paths["minus"],
        zero_hall_recipe=output_paths.get("zero"),
    )
    if not output_audit.compatible:
        raise ValueError("adjusted Hall suite failed consistency check after writing recipes")

    safety = load_named_safety_preset(input_recipes["longitudinal"].safety_preset, safety_dir)
    review_path = out / f"{prefix}_adjustment_review.md"
    if review_path.exists() and not overwrite:
        raise FileExistsError(f"Adjustment review already exists: {review_path}")
    review_path.write_text(
        format_dual_gate_lockin_hall_suite_adjustment_review(
            input_audit,
            output_audit,
            safety,
            adjustment_note=adjustment_note,
        ),
        encoding="utf-8",
    )
    return HallSuiteAdjustmentResult(
        out,
        output_paths["longitudinal"],
        output_paths["plus"],
        output_paths["minus"],
        output_paths.get("zero"),
        review_path,
    )


def write_dual_gate_lockin_hall_suite_acquisition_package(
    longitudinal_recipe: str | Path,
    plus_hall_recipe: str | Path,
    minus_hall_recipe: str | Path,
    output_dir: str | Path,
    *,
    zero_hall_recipe: str | Path | None = None,
    package_name: str | None = None,
    chunk_size: int,
    max_hardware_points: int = 9,
    accepted_previous_run: str | Path | None = None,
    chunk_feedback_files: list[str | Path] | None = None,
    preflight_files: list[str | Path] | None = None,
    note_files: list[str | Path] | None = None,
    four_terminal_ac_smoke_intake_json: str | Path | None = None,
    acquisition_note: str | None = None,
    safety_dir: str | Path = "configs/safety",
    overwrite: bool = False,
) -> HallSuiteAcquisitionPackageResult:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if max_hardware_points <= 0:
        raise ValueError("max_hardware_points must be positive")
    audit = audit_dual_gate_lockin_hall_suite(
        longitudinal_recipe,
        plus_hall_recipe,
        minus_hall_recipe,
        zero_hall_recipe=zero_hall_recipe,
    )
    if not audit.compatible:
        raise ValueError("input Hall suite is not compatible; run dual-gate-lockin-hall-suite-check first")

    recipes = _load_suite_recipes(audit)
    base_name = package_name or f"{recipes['longitudinal'].measurement_name}_acquisition_package"
    package_dir = Path(output_dir) / _safe_name(base_name)
    if package_dir.exists():
        if not overwrite:
            raise FileExistsError(f"Acquisition package already exists: {package_dir}")
        shutil.rmtree(package_dir)
    package_dir.mkdir(parents=True, exist_ok=False)

    recipes_dir = package_dir / "recipes"
    recipes_dir.mkdir()
    copied_recipes = _copy_suite_recipes(audit, recipes_dir)
    keithley_audits = _write_hall_suite_keithley_audits(copied_recipes, package_dir)
    lockin_audits = _write_hall_suite_lockin_audits(copied_recipes, package_dir)
    topology_contract = _hall_suite_topology_contract(recipes)
    extras = []
    extras.extend(_copy_labeled_files(chunk_feedback_files or [], package_dir / "chunk_feedback", "chunk_feedback"))
    extras.extend(_copy_labeled_files(preflight_files or [], package_dir / "preflight", "preflight"))
    extras.extend(_copy_labeled_files(note_files or [], package_dir / "notes", "note"))
    prerequisites = {}
    if four_terminal_ac_smoke_intake_json is not None:
        prerequisites["four_terminal_ac_smoke_intake"] = _copy_four_terminal_ac_smoke_intake(
            four_terminal_ac_smoke_intake_json,
            package_dir,
        )

    safety = load_named_safety_preset(recipes["longitudinal"].safety_preset, safety_dir)
    runbook_path = package_dir / "acquisition_runbook.md"
    runbook_path.write_text(
        format_dual_gate_lockin_hall_suite_acquisition_package_runbook(
            audit,
            copied_recipes,
            recipes,
            safety,
            chunk_size=chunk_size,
            max_hardware_points=max_hardware_points,
            accepted_previous_run=accepted_previous_run,
            acquisition_note=acquisition_note,
            extras=extras,
            prerequisites=prerequisites,
            keithley_audits=keithley_audits,
            lockin_audits=lockin_audits,
            topology_contract=topology_contract,
        ),
        encoding="utf-8",
    )
    manifest_path = package_dir / "package_manifest.json"
    measurement_condition_audits = _measurement_condition_audits_manifest(keithley_audits, lockin_audits)
    manifest = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "package_name": base_name,
        "manifest_schema_version": 2,
        "source_recipes": {
            "longitudinal": str(audit.longitudinal_recipe),
            "plus_hall": str(audit.plus_hall_recipe),
            "minus_hall": str(audit.minus_hall_recipe),
            "zero_hall": str(audit.zero_hall_recipe) if audit.zero_hall_recipe is not None else None,
        },
        "copied_recipes": {key: path.relative_to(package_dir).as_posix() for key, path in copied_recipes.items()},
        "keithley_parameter_audits": keithley_audits,
        "lockin_setting_audits": lockin_audits,
        "measurement_condition_audits": measurement_condition_audits,
        "topology_contract": topology_contract,
        "compatible": audit.compatible,
        "point_count": audit.point_count,
        "chunk_size": chunk_size,
        "max_hardware_points": max_hardware_points,
        "accepted_previous_run": str(accepted_previous_run) if accepted_previous_run is not None else None,
        "acquisition_note": acquisition_note,
        "prerequisites": prerequisites,
        "extras": extras,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    zip_path = Path(shutil.make_archive(str(package_dir), "zip", root_dir=package_dir))
    return HallSuiteAcquisitionPackageResult(package_dir, recipes_dir, runbook_path, manifest_path, zip_path)


def write_dual_gate_lockin_hall_suite_approved_next_scan_package(
    longitudinal_recipe: str | Path,
    plus_hall_recipe: str | Path,
    minus_hall_recipe: str | Path,
    output_dir: str | Path,
    *,
    proposal_json: str | Path,
    approval_review: str | Path,
    zero_hall_recipe: str | Path | None = None,
    package_name: str | None = None,
    chunk_size: int,
    max_hardware_points: int = 9,
    accepted_previous_run: str | Path | None = None,
    four_terminal_ac_smoke_intake_json: str | Path | None = None,
    acquisition_note: str | None = None,
    safety_dir: str | Path = "configs/safety",
    overwrite: bool = False,
) -> HallSuiteAcquisitionPackageResult:
    proposal_path = Path(proposal_json)
    review_path = Path(approval_review)
    if not proposal_path.exists() or not proposal_path.is_file():
        raise FileNotFoundError(f"Approved next-scan proposal JSON does not exist: {proposal_path}")
    if not review_path.exists() or not review_path.is_file():
        raise FileNotFoundError(f"Approved next-scan review does not exist: {review_path}")
    proposal = _load_next_scan_proposal_json(proposal_path)
    if proposal.get("requires_lab_approval") is not True:
        raise ValueError("next-scan proposal does not declare requires_lab_approval=true")
    note = acquisition_note or "approved next-scan acquisition package"
    result = write_dual_gate_lockin_hall_suite_acquisition_package(
        longitudinal_recipe,
        plus_hall_recipe,
        minus_hall_recipe,
        output_dir,
        zero_hall_recipe=zero_hall_recipe,
        package_name=package_name,
        chunk_size=chunk_size,
        max_hardware_points=max_hardware_points,
        accepted_previous_run=accepted_previous_run,
        note_files=[proposal_path, review_path],
        four_terminal_ac_smoke_intake_json=four_terminal_ac_smoke_intake_json,
        acquisition_note=note,
        safety_dir=safety_dir,
        overwrite=overwrite,
    )
    _annotate_approved_next_scan_package(result, proposal_path, review_path, proposal)
    if result.zip_path.exists():
        result.zip_path.unlink()
    zip_path = Path(shutil.make_archive(str(result.package_dir), "zip", root_dir=result.package_dir))
    return HallSuiteAcquisitionPackageResult(
        result.package_dir,
        result.recipes_dir,
        result.runbook_path,
        result.manifest_path,
        zip_path,
    )


def write_dual_gate_lockin_hall_suite_result_intake(
    package_manifest_or_dir: str | Path,
    longitudinal_run_dir: str | Path,
    plus_hall_run_dir: str | Path,
    minus_hall_run_dir: str | Path,
    *,
    zero_hall_run_dir: str | Path | None = None,
    output_path: str | Path | None = None,
    json_output_path: str | Path | None = None,
    require_lockin_settings: bool = True,
    overwrite: bool = False,
) -> HallSuiteResultIntake:
    manifest_path = _resolve_package_manifest_path(package_manifest_or_dir)
    manifest = _load_package_manifest(manifest_path)
    package_dir = manifest_path.parent
    recipe_paths = _package_recipe_paths(manifest, package_dir)
    if zero_hall_run_dir is not None and "zero" not in recipe_paths:
        raise ValueError("zero_hall_run_dir was supplied but the package has no zero-field recipe")

    issues: list[HallSuiteResultIntakeIssue] = []
    suite_audit = audit_dual_gate_lockin_hall_suite(
        recipe_paths["longitudinal"],
        recipe_paths["plus"],
        recipe_paths["minus"],
        zero_hall_recipe=recipe_paths.get("zero"),
    )
    if not suite_audit.compatible:
        issues.append(HallSuiteResultIntakeIssue("error", "package_suite", "packaged recipe suite is not compatible"))

    run_dirs = {
        "longitudinal": Path(longitudinal_run_dir),
        "plus": Path(plus_hall_run_dir),
        "minus": Path(minus_hall_run_dir),
    }
    if zero_hall_run_dir is not None:
        run_dirs["zero"] = Path(zero_hall_run_dir)
    elif "zero" in recipe_paths:
        issues.append(HallSuiteResultIntakeIssue("warning", "zero_run", "package includes a zero-field recipe but no zero-field run was supplied"))

    run_audits = {
        key: audit_dual_gate_lockin_run(path, require_lockin_settings=require_lockin_settings)
        for key, path in run_dirs.items()
    }
    for key, audit in run_audits.items():
        if not audit.accepted:
            issues.append(HallSuiteResultIntakeIssue("error", f"{key}.run_acceptance", "run failed strict acceptance audit"))
        issues.extend(_compare_run_to_packaged_recipe(key, run_dirs[key], recipe_paths[key]))

    role_fields = _run_role_fields(run_dirs)
    _check_intake_roles(role_fields, issues)
    if "plus" in role_fields and "minus" in role_fields:
        plus_b = role_fields["plus"].get("magnetic_field_t")
        minus_b = role_fields["minus"].get("magnetic_field_t")
        if isinstance(plus_b, (int, float)) and isinstance(minus_b, (int, float)):
            if plus_b <= 0 or minus_b >= 0 or abs(plus_b + minus_b) > max(1e-12, abs(plus_b) * 1e-9):
                issues.append(HallSuiteResultIntakeIssue("error", "run_magnetic_field", "+B and -B runs do not have equal-magnitude opposite fields"))
    run_topologies = {key: _run_topology_summary(run_dirs[key]) for key in run_audits}

    errors = [issue for issue in issues if issue.severity == "error"]
    accepted = not errors
    report_text = format_dual_gate_lockin_hall_suite_result_intake(
        manifest_path,
        manifest,
        suite_audit,
        run_audits,
        run_topologies,
        issues,
        accepted=accepted,
    )
    report_path = Path(output_path) if output_path is not None else package_dir / "result_intake_report.md"
    json_path = Path(json_output_path) if json_output_path is not None else package_dir / "result_intake.json"
    for path in [report_path, json_path]:
        if path.exists() and not overwrite:
            raise FileExistsError(f"Result intake output already exists: {path}")
        path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report_text, encoding="utf-8")
    json_payload = {
        "package_manifest_path": str(manifest_path),
        "accepted": accepted,
        "issues": [issue.__dict__ for issue in issues],
        "runs": {
            key: {
                "run_dir": str(audit.run_dir),
                "accepted": audit.accepted,
                "completed": audit.completed,
                "points_written": audit.points_written,
                "planned_points": audit.planned_points,
                "remaining_points": audit.remaining_points,
                "topology": run_topologies.get(key),
            }
            for key, audit in run_audits.items()
        },
    }
    json_path.write_text(json.dumps(json_payload, indent=2, sort_keys=True), encoding="utf-8")
    return HallSuiteResultIntake(manifest_path, accepted, report_path, json_path, tuple(issues))


def write_dual_gate_lockin_hall_suite_analysis(
    result_intake_json_or_package_dir: str | Path,
    *,
    output_dir: str | Path | None = None,
    value_column: HallValueColumn = "lockin_x_v",
    prefer_zero_corrected: bool = True,
    overwrite: bool = False,
) -> HallSuiteAnalysisResult:
    intake_json_path = _resolve_result_intake_json_path(result_intake_json_or_package_dir)
    intake = _load_result_intake_json(intake_json_path)
    if intake.get("accepted") is not True:
        raise ValueError("Hall suite result intake is not accepted; run/fix dual-gate-lockin-hall-suite-intake first")
    manifest_path_for_drift = _package_manifest_path_from_intake(intake_json_path, intake)
    drift_payload = _build_condition_drift_payload(manifest_path_for_drift, intake_json_path)
    if drift_payload.get("accepted") is not True:
        raise ValueError("Hall suite acquisition-condition drift audit failed; run/fix dual-gate-lockin-hall-suite-condition-drift first")
    runs = intake.get("runs")
    if not isinstance(runs, dict):
        raise ValueError("result_intake.json is missing runs")
    required = ["longitudinal", "plus", "minus"]
    for key in required:
        if key not in runs or not isinstance(runs[key], dict) or not runs[key].get("run_dir"):
            raise ValueError(f"result_intake.json is missing run_dir for {key}")
    longitudinal_run = Path(runs["longitudinal"]["run_dir"])
    plus_run = Path(runs["plus"]["run_dir"])
    minus_run = Path(runs["minus"]["run_dir"])
    zero_run = Path(runs["zero"]["run_dir"]) if isinstance(runs.get("zero"), dict) and runs["zero"].get("run_dir") else None

    package_dir = intake_json_path.parent
    out = Path(output_dir) if output_dir is not None else package_dir / "hall_analysis"
    if out.exists() and any(out.iterdir()) and not overwrite:
        raise FileExistsError(f"Hall suite analysis output already exists and is not empty: {out}")
    out.mkdir(parents=True, exist_ok=True)

    antisym = write_dual_gate_lockin_hall_antisym(
        plus_run,
        minus_run,
        output_dir=out / "antisym",
        value_column=value_column,
        overwrite=overwrite,
    )
    zero_corrected = None
    hall_density_source = antisym.output_csv
    if zero_run is not None:
        zero_corrected = write_dual_gate_lockin_hall_zero_corrected(
            plus_run,
            zero_run,
            output_dir=out / "zero_corrected",
            value_column=value_column,
            overwrite=overwrite,
        )
        if prefer_zero_corrected:
            hall_density_source = zero_corrected.output_csv
    mobility = write_dual_gate_lockin_hall_mobility(
        hall_density_source,
        longitudinal_run,
        output_dir=out / "mobility",
        overwrite=overwrite,
    )
    manifest_path = out / "hall_suite_analysis_manifest.json"
    if manifest_path.exists() and not overwrite:
        raise FileExistsError(f"Hall suite analysis manifest already exists: {manifest_path}")
    manifest = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "result_intake_json": str(intake_json_path),
        "value_column": value_column,
        "prefer_zero_corrected": prefer_zero_corrected,
        "hall_density_source": str(hall_density_source),
        "runs": {
            "longitudinal": str(longitudinal_run),
            "plus": str(plus_run),
            "minus": str(minus_run),
            "zero": str(zero_run) if zero_run is not None else None,
        },
        "outputs": {
            "antisym_csv": str(antisym.output_csv),
            "antisym_report": str(antisym.report_path),
            "zero_corrected_csv": str(zero_corrected.output_csv) if zero_corrected is not None else None,
            "zero_corrected_report": str(zero_corrected.report_path) if zero_corrected is not None else None,
            "mobility_csv": str(mobility.output_csv),
            "mobility_report": str(mobility.report_path),
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    report_path = out / "hall_suite_analysis_report.md"
    if report_path.exists() and not overwrite:
        raise FileExistsError(f"Hall suite analysis report already exists: {report_path}")
    report_path.write_text(format_dual_gate_lockin_hall_suite_analysis_report(manifest), encoding="utf-8")
    return HallSuiteAnalysisResult(
        output_dir=out,
        antisym_dir=antisym.output_csv.parent,
        zero_corrected_dir=zero_corrected.output_csv.parent if zero_corrected is not None else None,
        mobility_dir=mobility.output_csv.parent,
        report_path=report_path,
        manifest_path=manifest_path,
    )


def write_dual_gate_lockin_hall_suite_condition_drift_audit(
    package_manifest_or_dir: str | Path,
    *,
    result_intake_json: str | Path | None = None,
    output_path: str | Path | None = None,
    json_output_path: str | Path | None = None,
    overwrite: bool = False,
) -> HallSuiteConditionDriftAudit:
    manifest_path = _resolve_package_manifest_path(package_manifest_or_dir)
    package_dir = manifest_path.parent
    intake_path = _resolve_result_intake_json_path(result_intake_json or package_dir)
    payload = _build_condition_drift_payload(manifest_path, intake_path)
    report_text = format_dual_gate_lockin_hall_suite_condition_drift_audit(payload)
    report_path = Path(output_path) if output_path is not None else package_dir / "condition_drift_report.md"
    json_path = Path(json_output_path) if json_output_path is not None else package_dir / "condition_drift.json"
    for path in [report_path, json_path]:
        if path.exists() and not overwrite:
            raise FileExistsError(f"Condition drift output already exists: {path}")
        path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report_text, encoding="utf-8")
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return HallSuiteConditionDriftAudit(
        package_manifest_path=manifest_path,
        result_intake_json_path=intake_path,
        accepted=bool(payload["accepted"]),
        report_path=report_path,
        json_path=json_path,
        issues=tuple(HallSuiteConditionDriftIssue(**issue) for issue in payload["issues"]),
    )


def format_dual_gate_lockin_hall_suite_condition_drift_audit(payload: dict[str, Any]) -> str:
    status = "PASS" if payload.get("accepted") else "FAIL"
    lines = [
        "# Hall Suite Acquisition-Condition Drift Audit",
        "",
        f"- Status: {status}",
        f"- Package manifest: `{payload.get('package_manifest_path')}`",
        f"- Result intake JSON: `{payload.get('result_intake_json_path')}`",
        "",
        "## Runs",
        "",
    ]
    runs = payload.get("runs") if isinstance(payload.get("runs"), dict) else {}
    if runs:
        for key, run in runs.items():
            lines.append(f"- {key}: `{run.get('run_dir')}`")
    else:
        lines.append("- none")
    lines.extend(["", "## Drift Issues", ""])
    issues = payload.get("issues") if isinstance(payload.get("issues"), list) else []
    if not issues:
        lines.append("- none")
    else:
        for issue in issues:
            lines.append(
                f"- [{issue.get('severity')}] {issue.get('run_key')}.{issue.get('field')}: "
                f"{issue.get('message')} expected={issue.get('expected')!r} actual={issue.get('actual')!r}"
            )
    lines.extend(
        [
            "",
            "## Measurement-Condition Reminder",
            "",
            "Keithley NPLC/ranges/compliance/source-delay and SR860 settings are measurement conditions.",
            "If this audit fails, regenerate the package or repeat the run before comparing Hall scans.",
            "",
        ]
    )
    return "\n".join(lines)


def write_dual_gate_lockin_hall_suite_condition_snapshot_report(
    package_manifest_or_dir: str | Path,
    *,
    result_intake_json: str | Path | None = None,
    output_path: str | Path | None = None,
    json_output_path: str | Path | None = None,
    overwrite: bool = False,
) -> HallSuiteConditionSnapshotReport:
    manifest_path = _resolve_package_manifest_path(package_manifest_or_dir)
    package_dir = manifest_path.parent
    intake_path = _resolve_result_intake_json_path(result_intake_json or package_dir)
    payload = _build_condition_snapshot_payload(manifest_path, intake_path)
    report_text = format_dual_gate_lockin_hall_suite_condition_snapshot_report(payload)
    report_path = Path(output_path) if output_path is not None else package_dir / "condition_snapshot_report.md"
    json_path = Path(json_output_path) if json_output_path is not None else package_dir / "condition_snapshot.json"
    for path in [report_path, json_path]:
        if path.exists() and not overwrite:
            raise FileExistsError(f"Condition snapshot output already exists: {path}")
        path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report_text, encoding="utf-8")
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return HallSuiteConditionSnapshotReport(
        package_manifest_path=manifest_path,
        result_intake_json_path=intake_path,
        report_path=report_path,
        json_path=json_path,
        run_count=len(payload.get("runs") or []),
    )


def format_dual_gate_lockin_hall_suite_condition_snapshot_report(payload: dict[str, Any]) -> str:
    lines = [
        "# Hall Suite Run Condition Snapshot",
        "",
        f"- Package manifest: `{payload.get('package_manifest_path')}`",
        f"- Result intake JSON: `{payload.get('result_intake_json_path')}`",
        f"- Run count: {len(payload.get('runs') or [])}",
        "",
        "## Keithley Gate Settings",
        "",
        "| Run | Gate | Address | Terminal | V range (V) | I range (A) | NPLC | Compliance (A) | Source delay (s) | Readback matched |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    runs = payload.get("runs") if isinstance(payload.get("runs"), list) else []
    for run in runs:
        for gate in ["gate1", "gate2"]:
            gate_data = run.get(gate) if isinstance(run.get(gate), dict) else {}
            lines.append(
                "| "
                f"{run.get('run_key')} | {gate} | `{gate_data.get('address')}` | "
                f"{_fmt_optional(gate_data.get('terminal'))} | "
                f"{_fmt_optional(gate_data.get('voltage_range_v'))} | "
                f"{_fmt_optional(gate_data.get('current_range_a'))} | "
                f"{_fmt_optional(gate_data.get('nplc'))} | "
                f"{_fmt_optional(gate_data.get('current_compliance_a'))} | "
                f"{_fmt_optional(gate_data.get('source_delay_s'))} | "
                f"{_fmt_optional(gate_data.get('readback_matched'))} |"
            )
    lines.extend(
        [
            "",
            "## SR860 Settings",
            "",
            "| Run | Address | Sensitivity index | Time constant index | Read settle (s) | Time constant (s) | Readback available | Readback matched |",
            "| --- | --- | ---: | ---: | ---: | ---: | --- | --- |",
        ]
    )
    for run in runs:
        lockin = run.get("lockin") if isinstance(run.get("lockin"), dict) else {}
        lines.append(
            "| "
            f"{run.get('run_key')} | `{lockin.get('address')}` | "
            f"{_fmt_optional(lockin.get('sensitivity_index'))} | "
            f"{_fmt_optional(lockin.get('time_constant_index'))} | "
            f"{_fmt_optional(lockin.get('read_settle_s'))} | "
            f"{_fmt_optional(lockin.get('time_constant_s'))} | "
            f"{_fmt_optional(lockin.get('readback_available'))} | "
            f"{_fmt_optional(lockin.get('readback_matched'))} |"
        )
    lines.extend(
        [
            "",
            "## Hall-Bar Topology",
            "",
            "| Run | Role | B (T) | Excitation contacts | SR860 voltage contacts | Channel L (m) | Channel W (m) | Bias resistor (ohm) | Layout |",
            "| --- | --- | ---: | --- | --- | ---: | ---: | ---: | --- |",
        ]
    )
    for run in runs:
        topology = run.get("topology") if isinstance(run.get("topology"), dict) else {}
        lines.append(
            "| "
            f"{run.get('run_key')} | "
            f"{_fmt_optional(topology.get('voltage_probe_role'))} | "
            f"{_fmt_optional(topology.get('magnetic_field_t'))} | "
            f"{_fmt_contact_list(topology.get('excitation_contacts'))} | "
            f"{_fmt_contact_list(topology.get('lockin_input_contacts'))} | "
            f"{_fmt_optional(topology.get('channel_length_m'))} | "
            f"{_fmt_optional(topology.get('channel_width_m'))} | "
            f"{_fmt_optional(topology.get('bias_resistor_ohm'))} | "
            f"{_fmt_optional(topology.get('topology_layout'))} |"
        )
    lines.extend(
        [
            "",
            "## Reminder",
            "",
            "Use this snapshot as a lab-notebook table before Hall analysis. NPLC, ranges, compliance, source delay, SR860 settings, and Hall-bar contact topology are measurement conditions.",
            "",
        ]
    )
    return "\n".join(lines)


def format_dual_gate_lockin_hall_suite_analysis_report(manifest: dict[str, Any]) -> str:
    outputs = manifest.get("outputs") or {}
    runs = manifest.get("runs") or {}
    return "\n".join(
        [
            "# Dual-Gate Lock-In Hall Suite Analysis",
            "",
            f"- Result intake JSON: `{manifest.get('result_intake_json')}`",
            f"- Value column: `{manifest.get('value_column')}`",
            f"- Hall density source: `{manifest.get('hall_density_source')}`",
            f"- Prefer zero-corrected density: {manifest.get('prefer_zero_corrected')}",
            "",
            "## Runs",
            "",
            f"- Longitudinal Vxx: `{runs.get('longitudinal')}`",
            f"- +B Vxy: `{runs.get('plus')}`",
            f"- -B Vxy: `{runs.get('minus')}`",
            f"- 0B Vxy: `{runs.get('zero') or 'not supplied'}`",
            "",
            "## Outputs",
            "",
            f"- Antisym CSV: `{outputs.get('antisym_csv')}`",
            f"- Antisym report: `{outputs.get('antisym_report')}`",
            f"- Zero-corrected CSV: `{outputs.get('zero_corrected_csv') or 'not written'}`",
            f"- Zero-corrected report: `{outputs.get('zero_corrected_report') or 'not written'}`",
            f"- Mobility CSV: `{outputs.get('mobility_csv')}`",
            f"- Mobility report: `{outputs.get('mobility_report')}`",
            "",
            "## Gate",
            "",
            "This analysis was allowed only because the supplied result intake JSON was accepted.",
            "",
        ]
    )


def write_dual_gate_lockin_hall_suite_analysis_review(
    analysis_dir: str | Path,
    *,
    output: str | Path | None = None,
    json_output: str | Path | None = None,
    overwrite: bool = False,
) -> HallSuiteAnalysisReview:
    analysis_path = Path(analysis_dir)
    if not analysis_path.exists() or not analysis_path.is_dir():
        raise FileNotFoundError(f"Hall suite analysis directory does not exist: {analysis_path}")
    report_path = Path(output) if output is not None else analysis_path / "hall_suite_analysis_review.md"
    json_path = Path(json_output) if json_output is not None else analysis_path / "hall_suite_analysis_review.json"
    if report_path.exists() and not overwrite:
        raise FileExistsError(f"Hall suite analysis review report already exists: {report_path}")
    if json_path.exists() and not overwrite:
        raise FileExistsError(f"Hall suite analysis review JSON already exists: {json_path}")

    manifest_path = analysis_path / "hall_suite_analysis_manifest.json"
    issues: list[HallSuiteAnalysisReviewIssue] = []
    manifest: dict[str, Any] = {}
    if not manifest_path.exists():
        issues.append(HallSuiteAnalysisReviewIssue("error", "manifest.exists", f"missing analysis manifest: {manifest_path}"))
    else:
        try:
            loaded_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if isinstance(loaded_manifest, dict):
                manifest = loaded_manifest
            else:
                issues.append(HallSuiteAnalysisReviewIssue("error", "manifest.type", "analysis manifest must contain a JSON object"))
        except json.JSONDecodeError as exc:
            issues.append(HallSuiteAnalysisReviewIssue("error", "manifest.parse", f"could not parse analysis manifest: {exc}"))

    outputs = manifest.get("outputs") if isinstance(manifest.get("outputs"), dict) else {}
    antisym_csv = _analysis_csv_path(analysis_path, outputs.get("antisym_csv"), "antisym/hall_antisym.csv")
    zero_corrected_csv = _analysis_csv_path(analysis_path, outputs.get("zero_corrected_csv"), "zero_corrected/hall_zero_corrected.csv")
    mobility_csv = _analysis_csv_path(analysis_path, outputs.get("mobility_csv"), "mobility/hall_mobility.csv")

    antisym_rows = _read_analysis_rows(antisym_csv, HALL_ANTISYM_COLUMNS, "antisym_csv", issues, required=True)
    zero_rows = _read_analysis_rows(zero_corrected_csv, HALL_ZERO_CORRECTED_COLUMNS, "zero_corrected_csv", issues, required=False)
    mobility_rows = _read_analysis_rows(mobility_csv, HALL_MOBILITY_COLUMNS, "mobility_csv", issues, required=True)

    summary = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "analysis_dir": str(analysis_path),
        "manifest_path": str(manifest_path),
        "files": {
            "antisym_csv": str(antisym_csv),
            "zero_corrected_csv": str(zero_corrected_csv) if zero_corrected_csv is not None else None,
            "mobility_csv": str(mobility_csv),
        },
        "antisym": _analysis_table_summary(
            antisym_rows,
            {
                "hall_antisym_resistance_ohm": "hall_antisym_resistance_ohm",
                "field_even_resistance_ohm": "field_even_resistance_ohm",
                "hall_carrier_density_per_m2": "hall_carrier_density_per_m2",
            },
        ),
        "zero_corrected": _analysis_table_summary(
            zero_rows,
            {
                "hall_zero_corrected_resistance_ohm": "hall_zero_corrected_resistance_ohm",
                "zero_field_resistance_ohm": "zero_field_resistance_ohm",
                "hall_carrier_density_per_m2": "hall_carrier_density_per_m2",
            },
        ),
        "mobility": _analysis_table_summary(
            mobility_rows,
            {
                "hall_carrier_density_per_m2": "hall_carrier_density_per_m2",
                "longitudinal_sheet_conductivity_s_per_sq": "longitudinal_sheet_conductivity_s_per_sq",
                "longitudinal_sheet_resistance_ohm_per_sq": "longitudinal_sheet_resistance_ohm_per_sq",
                "mobility_signed_m2_per_v_s": "mobility_signed_m2_per_v_s",
                "mobility_magnitude_cm2_per_v_s": "mobility_magnitude_cm2_per_v_s",
            },
        ),
    }
    _append_hall_suite_analysis_review_issues(antisym_rows, zero_rows, mobility_rows, issues)
    accepted = not any(issue.severity == "error" for issue in issues)
    payload = {
        "accepted_for_next_scan_decision": accepted,
        "summary": summary,
        "issues": [issue.__dict__ for issue in issues],
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(format_dual_gate_lockin_hall_suite_analysis_review(payload), encoding="utf-8")
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return HallSuiteAnalysisReview(analysis_path, accepted, report_path, json_path, tuple(issues))


def format_dual_gate_lockin_hall_suite_analysis_review(payload: dict[str, Any]) -> str:
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    issues = payload.get("issues") if isinstance(payload.get("issues"), list) else []
    lines = [
        "# Dual-Gate Lock-In Hall Suite Analysis Review",
        "",
        f"- Analysis directory: `{summary.get('analysis_dir')}`",
        f"- Ready for next-scan decision: {payload.get('accepted_for_next_scan_decision')}",
        "",
        "## Artifact Summary",
        "",
        "| Artifact | Gate points | Columns reviewed |",
        "| --- | ---: | --- |",
        _analysis_summary_table_row("Antisym", summary.get("antisym")),
        _analysis_summary_table_row("Zero-corrected", summary.get("zero_corrected")),
        _analysis_summary_table_row("Mobility", summary.get("mobility")),
        "",
        "## Key Ranges",
        "",
        "### Hall Antisym",
        "",
        *_analysis_range_lines(summary.get("antisym")),
        "",
        "### Zero-Corrected Hall",
        "",
        *_analysis_range_lines(summary.get("zero_corrected")),
        "",
        "### Mobility",
        "",
        *_analysis_range_lines(summary.get("mobility")),
        "",
        "## Issues For Next Scan Decision",
        "",
    ]
    if issues:
        lines.extend(f"- [{issue.get('severity')}] {issue.get('check')}: {issue.get('message')}" for issue in issues)
    else:
        lines.append("- No automatic review issues were found.")
    lines.extend(
        [
            "",
            "## Lab Decision Notes",
            "",
            "- Treat warnings as prompts for human review, not automatic rejection.",
            "- If carrier density changes sign, inspect whether the scan crossed the charge neutrality point or whether Hall polarity/contact labeling is wrong.",
            "- If field-even or zero-field offsets are large, review contact asymmetry, lock-in phase, magnetic-field settling, and wiring before expanding the gate window.",
            "- Keep Keithley NPLC, current range, voltage range, compliance, source delay, and SR860 settings fixed when comparing repeated scans unless the lab deliberately changes them.",
            "",
        ]
    )
    return "\n".join(lines)


def write_dual_gate_lockin_hall_suite_next_scan_proposal(
    review_json_or_analysis_dir: str | Path,
    *,
    output: str | Path | None = None,
    json_output: str | Path | None = None,
    overwrite: bool = False,
) -> HallSuiteNextScanProposal:
    review_json_path = _resolve_analysis_review_json_path(review_json_or_analysis_dir)
    review = _load_analysis_review_json(review_json_path)
    if review.get("accepted_for_next_scan_decision") is not True:
        raise ValueError("Hall suite analysis review is not accepted for next-scan decision")
    summary = review.get("summary") if isinstance(review.get("summary"), dict) else {}
    analysis_dir = Path(str(summary.get("analysis_dir") or review_json_path.parent))
    proposal_path = Path(output) if output is not None else analysis_dir / "hall_suite_next_scan_proposal.md"
    proposal_json_path = Path(json_output) if json_output is not None else analysis_dir / "hall_suite_next_scan_proposal.json"
    if proposal_path.exists() and not overwrite:
        raise FileExistsError(f"Hall suite next-scan proposal report already exists: {proposal_path}")
    if proposal_json_path.exists() and not overwrite:
        raise FileExistsError(f"Hall suite next-scan proposal JSON already exists: {proposal_json_path}")

    files = summary.get("files") if isinstance(summary.get("files"), dict) else {}
    mobility_csv = Path(str(files.get("mobility_csv") or analysis_dir / "mobility" / "hall_mobility.csv"))
    rows = _read_required_csv(mobility_csv, HALL_MOBILITY_COLUMNS)
    grid = _proposal_grid_summary(rows)
    density_values = [_optional_float(row.get("hall_carrier_density_per_m2")) for row in rows]
    finite_density = [value for value in density_values if value is not None]
    review_issues = review.get("issues") if isinstance(review.get("issues"), list) else []
    proposed = _build_next_scan_gate_proposal(rows, grid, finite_density)
    settings = _proposal_preserved_settings(analysis_dir)
    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "review_json": str(review_json_path),
        "analysis_dir": str(analysis_dir),
        "accepted_for_recipe_generation": False,
        "hardware_recipe_written": False,
        "requires_lab_approval": True,
        "reason_recipe_not_written": "proposal is advisory; generate or edit recipes only after lab approval",
        "strategy": proposed["strategy"],
        "rationale": proposed["rationale"],
        "current_gate_grid": grid,
        "proposed_gate_grid": proposed["gate_grid"],
        "density_summary": _proposal_density_summary(finite_density),
        "review_warnings": [issue for issue in review_issues if isinstance(issue, dict) and issue.get("severity") == "warning"],
        "preserve_measurement_settings": settings,
        "next_commands": [
            "ptm dual-gate-lockin-hall-suite-adjust-recipes <suite>\\<prefix>_vxx.yaml <suite>\\<prefix>_vxy_plus_b.yaml <suite>\\<prefix>_vxy_minus_b.yaml <approved_output_suite> --zero-field-recipe <suite>\\<prefix>_vxy_zero_b.yaml --measurement-prefix <approved_prefix> --adjustment-note \"approved next-scan proposal\"",
            "ptm dual-gate-lockin-hall-suite-check <approved_output_suite>\\<prefix>_vxx.yaml <approved_output_suite>\\<prefix>_vxy_plus_b.yaml <approved_output_suite>\\<prefix>_vxy_minus_b.yaml --zero-field-recipe <approved_output_suite>\\<prefix>_vxy_zero_b.yaml",
            "ptm dual-gate-lockin-hall-suite-package <approved recipes...> data\\hall_packages --chunk-size <N> --package-name <approved_package>",
        ],
    }
    proposal_path.parent.mkdir(parents=True, exist_ok=True)
    proposal_json_path.parent.mkdir(parents=True, exist_ok=True)
    proposal_path.write_text(format_dual_gate_lockin_hall_suite_next_scan_proposal(payload), encoding="utf-8")
    proposal_json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return HallSuiteNextScanProposal(review_json_path, False, proposal_path, proposal_json_path)


def format_dual_gate_lockin_hall_suite_next_scan_proposal(payload: dict[str, Any]) -> str:
    current = payload.get("current_gate_grid") if isinstance(payload.get("current_gate_grid"), dict) else {}
    proposed = payload.get("proposed_gate_grid") if isinstance(payload.get("proposed_gate_grid"), dict) else {}
    density = payload.get("density_summary") if isinstance(payload.get("density_summary"), dict) else {}
    warnings = payload.get("review_warnings") if isinstance(payload.get("review_warnings"), list) else []
    settings = payload.get("preserve_measurement_settings") if isinstance(payload.get("preserve_measurement_settings"), dict) else {}
    lines = [
        "# Dual-Gate Lock-In Hall Suite Next-Scan Proposal",
        "",
        f"- Review JSON: `{payload.get('review_json')}`",
        f"- Strategy: `{payload.get('strategy')}`",
        f"- Hardware recipe written: {payload.get('hardware_recipe_written')}",
        f"- Accepted for recipe generation: {payload.get('accepted_for_recipe_generation')}",
        f"- Requires lab approval: {payload.get('requires_lab_approval')}",
        "",
        "## Rationale",
        "",
        f"- {payload.get('rationale')}",
        "",
        "## Gate Grid",
        "",
        "| Axis | Current start (V) | Current stop (V) | Current points | Proposed start (V) | Proposed stop (V) | Proposed points |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        _proposal_grid_row("gate1", current, proposed),
        _proposal_grid_row("gate2", current, proposed),
        "",
        "## Density Summary",
        "",
        f"- Finite density points: {density.get('finite_count', 0)}",
        f"- Min density (m^-2): {_fmt_optional(density.get('min'))}",
        f"- Max density (m^-2): {_fmt_optional(density.get('max'))}",
        f"- Contains positive density: {density.get('has_positive')}",
        f"- Contains negative density: {density.get('has_negative')}",
        "",
        "## Review Warnings Carried Forward",
        "",
    ]
    if warnings:
        lines.extend(f"- [{issue.get('check')}] {issue.get('message')}" for issue in warnings if isinstance(issue, dict))
    else:
        lines.append("- No review warnings were carried forward.")
    lines.extend(
        [
            "",
            "## Measurement Settings To Preserve",
            "",
            *_proposal_settings_lines(settings),
            "",
            "## Lab Approval Gate",
            "",
            "- This command intentionally did not write hardware recipes.",
            "- Approve the proposed gate window/spacing in the lab notebook before generating adjusted recipes.",
            "- Preserve Keithley NPLC, voltage range, current range, compliance, source delay, and SR860 settings unless the approval note explicitly changes them.",
            "",
            "## Suggested Next Commands After Approval",
            "",
            "```powershell",
            *[str(command) for command in payload.get("next_commands", [])],
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def write_dual_gate_lockin_hall_suite_approved_next_scan_recipes(
    proposal_json_or_analysis_dir: str | Path,
    output_dir: str | Path,
    *,
    approval_note: str,
    measurement_prefix: str | None = None,
    run_output_directory: str | Path | None = None,
    safety_dir: str | Path = "configs/safety",
    overwrite: bool = False,
) -> HallSuiteApprovedNextScanResult:
    if not approval_note or not approval_note.strip():
        raise ValueError("approval_note is required before writing next-scan hardware recipes")
    proposal_json_path = _resolve_next_scan_proposal_json_path(proposal_json_or_analysis_dir)
    proposal = _load_next_scan_proposal_json(proposal_json_path)
    if proposal.get("requires_lab_approval") is not True:
        raise ValueError("next-scan proposal does not declare a lab approval gate")
    if proposal.get("hardware_recipe_written") is not False:
        raise ValueError("next-scan proposal must be advisory and must not already mark hardware recipes as written")

    package_manifest_path = _proposal_package_manifest_path(proposal)
    package_manifest = _load_package_manifest(package_manifest_path)
    package_dir = package_manifest_path.parent
    recipe_paths = _package_recipe_paths(package_manifest, package_dir)
    audit = audit_dual_gate_lockin_hall_suite(
        recipe_paths["longitudinal"],
        recipe_paths["plus"],
        recipe_paths["minus"],
        zero_hall_recipe=recipe_paths.get("zero"),
    )
    if not audit.compatible:
        raise ValueError("packaged Hall suite is not compatible; cannot generate approved next-scan recipes")

    input_recipes = _load_suite_recipes(audit)
    prefix = measurement_prefix or f"{input_recipes['longitudinal'].measurement_name}_approved_next_scan"
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    proposed_grid = proposal.get("proposed_gate_grid") if isinstance(proposal.get("proposed_gate_grid"), dict) else {}
    output_paths: dict[str, Path] = {}
    for key, _, input_path, recipe in _suite_key_entries(audit, input_recipes):
        measurement_name = _suite_adjusted_measurement_name(prefix, recipe)
        output_path = out / f"{measurement_name}.yaml"
        data = _build_approved_next_scan_recipe_data(
            input_path,
            measurement_name=measurement_name,
            proposed_gate_grid=proposed_grid,
            approval_note=approval_note.strip(),
            output_directory=run_output_directory,
        )
        _write_recipe(output_path, data, overwrite=overwrite)
        output_paths[key] = output_path

    output_audit = audit_dual_gate_lockin_hall_suite(
        output_paths["longitudinal"],
        output_paths["plus"],
        output_paths["minus"],
        zero_hall_recipe=output_paths.get("zero"),
    )
    if not output_audit.compatible:
        raise ValueError("approved next-scan Hall suite failed consistency check after writing recipes")
    review_path = out / f"{prefix}_approved_next_scan_review.md"
    if review_path.exists() and not overwrite:
        raise FileExistsError(f"Approved next-scan review already exists: {review_path}")
    safety = load_named_safety_preset(input_recipes["longitudinal"].safety_preset, safety_dir)
    review_path.write_text(
        format_dual_gate_lockin_hall_suite_approved_next_scan_review(
            proposal_json_path,
            proposal,
            input_audit=audit,
            output_audit=output_audit,
            safety=safety,
            approval_note=approval_note.strip(),
        ),
        encoding="utf-8",
    )
    return HallSuiteApprovedNextScanResult(
        out,
        output_paths["longitudinal"],
        output_paths["plus"],
        output_paths["minus"],
        output_paths.get("zero"),
        review_path,
    )


def format_dual_gate_lockin_hall_suite_approved_next_scan_review(
    proposal_json_path: Path,
    proposal: dict[str, Any],
    *,
    input_audit: HallSuiteAudit,
    output_audit: HallSuiteAudit,
    safety: SafetyPreset,
    approval_note: str,
) -> str:
    current = proposal.get("current_gate_grid") if isinstance(proposal.get("current_gate_grid"), dict) else {}
    proposed = proposal.get("proposed_gate_grid") if isinstance(proposal.get("proposed_gate_grid"), dict) else {}
    return "\n".join(
        [
            "# Approved Hall-Suite Next-Scan Recipes",
            "",
            f"- Proposal JSON: `{proposal_json_path}`",
            f"- Strategy: `{proposal.get('strategy')}`",
            f"- Approval note: {approval_note}",
            f"- Safety preset: {safety.name}",
            "",
            "## Gate Grid Change",
            "",
            "| Axis | Previous start (V) | Previous stop (V) | Previous points | New start (V) | New stop (V) | New points |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
            _proposal_grid_row("gate1", current, proposed),
            _proposal_grid_row("gate2", current, proposed),
            "",
            "## Input Suite",
            "",
            "```text",
            format_hall_suite_audit(input_audit),
            "```",
            "",
            "## Output Suite",
            "",
            "```text",
            format_hall_suite_audit(output_audit),
            "```",
            "",
            "## Measurement Settings Policy",
            "",
            "- This generator only applies the approved gate grid from the proposal.",
            "- Keithley NPLC, voltage range, current range, compliance, source delay, and SR860 settings are copied from the packaged recipes.",
            "- If any of those measurement settings need to change, use the explicit adjustment workflow and record the reason in the lab notebook.",
            "",
            "## Required Before Hardware",
            "",
            "```powershell",
            (
                f"ptm dual-gate-lockin-hall-suite-check {output_audit.longitudinal_recipe} "
                f"{output_audit.plus_hall_recipe} {output_audit.minus_hall_recipe}"
                + (f" --zero-field-recipe {output_audit.zero_hall_recipe}" if output_audit.zero_hall_recipe is not None else "")
            ),
            (
                f"ptm dual-gate-lockin-hall-suite-package {output_audit.longitudinal_recipe} "
                f"{output_audit.plus_hall_recipe} {output_audit.minus_hall_recipe} data\\hall_packages --chunk-size <N> "
                f"--package-name <approved_package>"
                + (f" --zero-field-recipe {output_audit.zero_hall_recipe}" if output_audit.zero_hall_recipe is not None else "")
            ),
            "```",
            "",
        ]
    )


def format_dual_gate_lockin_hall_suite_result_intake(
    manifest_path: Path,
    manifest: dict[str, Any],
    suite_audit: HallSuiteAudit,
    run_audits: dict[str, Any],
    run_topologies: dict[str, dict[str, Any]],
    issues: list[HallSuiteResultIntakeIssue],
    *,
    accepted: bool,
) -> str:
    lines = [
        "# Dual-Gate Lock-In Hall Suite Result Intake",
        "",
        f"- Package manifest: `{manifest_path}`",
        f"- Package name: {manifest.get('package_name') or 'n/a'}",
        f"- Accepted for Hall analysis: {accepted}",
        f"- Expected point count per run: {manifest.get('point_count') or 'n/a'}",
        "",
        "## Packaged Recipe Suite",
        "",
        "```text",
        format_hall_suite_audit(suite_audit),
        "```",
        "",
        "## Run Acceptance",
        "",
    ]
    for key, audit in run_audits.items():
        lines.extend(
            [
                f"### {_suite_key_label(key)}",
                "",
                "```text",
                format_dual_gate_lockin_acceptance(audit),
                "```",
                "",
            ]
        )
    lines.extend(
        [
            "## Returned Run Topology",
            "",
            "| Run | Role | B (T) | Excitation contacts | SR860 voltage contacts | Channel L (m) | Channel W (m) | Layout |",
            "| --- | --- | ---: | --- | --- | ---: | ---: | --- |",
        ]
    )
    for key in run_audits:
        topology = run_topologies.get(key, {})
        lines.append(
            "| "
            f"{key} | "
            f"{_fmt_optional(topology.get('voltage_probe_role'))} | "
            f"{_fmt_optional(topology.get('magnetic_field_t'))} | "
            f"{_fmt_contact_list(topology.get('excitation_contacts'))} | "
            f"{_fmt_contact_list(topology.get('lockin_input_contacts'))} | "
            f"{_fmt_optional(topology.get('channel_length_m'))} | "
            f"{_fmt_optional(topology.get('channel_width_m'))} | "
            f"{_fmt_optional(topology.get('topology_layout'))} |"
        )
    lines.extend(["", "## Intake Issues", ""])
    if issues:
        for issue in issues:
            lines.append(f"- [{issue.severity}] {issue.check}: {issue.message}")
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Next Commands",
            "",
            "```powershell",
            "# Run these only after intake is accepted.",
            "ptm dual-gate-lockin-hall-antisym data\\raw\\<plus_B_run> data\\raw\\<minus_B_run> --output-dir data\\analysis\\<hall_antisym_folder>",
            "ptm dual-gate-lockin-hall-zero-correct data\\raw\\<plus_B_run> data\\raw\\<zero_B_run> --output-dir data\\analysis\\<hall_zero_corrected_folder>",
            "ptm dual-gate-lockin-hall-mobility data\\analysis\\<hall_density_folder> data\\raw\\<longitudinal_Vxx_run> --output-dir data\\analysis\\<hall_mobility_folder>",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def format_dual_gate_lockin_hall_suite_acquisition_package_runbook(
    audit: HallSuiteAudit,
    copied_recipes: dict[str, Path],
    recipes: dict[str, DualGateLockInRecipe],
    safety: SafetyPreset,
    *,
    chunk_size: int,
    max_hardware_points: int,
    accepted_previous_run: str | Path | None,
    acquisition_note: str | None,
    extras: list[dict[str, str]],
    prerequisites: dict[str, dict[str, Any]],
    keithley_audits: dict[str, dict[str, Any]],
    lockin_audits: dict[str, dict[str, Any]],
    topology_contract: dict[str, dict[str, Any]],
) -> str:
    copied_audit = audit_dual_gate_lockin_hall_suite(
        copied_recipes["longitudinal"],
        copied_recipes["plus"],
        copied_recipes["minus"],
        zero_hall_recipe=copied_recipes.get("zero"),
    )
    copied_suite = _suite_entries(copied_audit, _load_suite_recipes(copied_audit))
    zero_arg = f" --zero-field-recipe {copied_recipes['zero']}" if "zero" in copied_recipes else ""
    accepted = str(accepted_previous_run) if accepted_previous_run is not None else "data\\raw\\<accepted_run>"
    note = acquisition_note or "n/a"
    return "\n".join(
        [
            "# Dual-Gate Lock-In Hall Suite Acquisition Package",
            "",
            "## Purpose",
            "",
            "This package is hardware-free. Use it on the lab laptop to review the adjusted Hall suite, run preflight, execute bounded chunks, collect feedback, stitch completed chunks, and run Hall analysis.",
            "",
            "## Acquisition Note",
            "",
            note,
            "",
            "## Suite Consistency",
            "",
            "```text",
            format_hall_suite_audit(copied_audit),
            "```",
            "",
            "## Included Recipes",
            "",
            *[f"- {label}: `{path}`" for _, label, path, _ in copied_suite],
            "",
            "## Measurement Prerequisites",
            "",
            *_format_hall_suite_package_prerequisites(prerequisites),
            "",
            "## Topology Contract",
            "",
            "| Run | Role | B (T) | Excitation contacts | SR860 voltage contacts | Channel L (m) | Channel W (m) | Layout |",
            "| --- | --- | ---: | --- | --- | ---: | ---: | --- |",
            *_format_hall_suite_topology_contract_rows(topology_contract),
            "",
            "## Hardware-Free Checks",
            "",
            "```powershell",
            f"ptm dual-gate-lockin-hall-suite-check {copied_recipes['longitudinal']} {copied_recipes['plus']} {copied_recipes['minus']}{zero_arg}",
            f"ptm dual-gate-lockin-hall-suite-plan {copied_recipes['longitudinal']} {copied_recipes['plus']} {copied_recipes['minus']}{zero_arg}",
            f"ptm dual-gate-lockin-hall-suite-chunk-plan {copied_recipes['longitudinal']} {copied_recipes['plus']} {copied_recipes['minus']} --chunk-size {chunk_size} --max-hardware-points {max_hardware_points}{zero_arg}",
            *[f"ptm dual-gate-lockin-plan {path}" for _, _, path, _ in copied_suite],
            *[f"ptm dual-gate-lockin-preflight {path}" for _, _, path, _ in copied_suite],
            "```",
            "",
            "## Keithley Parameter Audits",
            "",
            *[
                (
                    f"- {label}: {'PASS' if record.get('ok_for_hardware') else 'MISSING'}; "
                    f"JSON `{record.get('json')}`, Markdown `{record.get('markdown')}`"
                )
                for label, record in keithley_audits.items()
            ],
            *([] if keithley_audits else ["- none"]),
            "",
            "## SR860 Measurement Parameter Audits",
            "",
            *[
                (
                    f"- {label}: {'PASS' if record.get('ok_for_hardware') else 'REVIEW'}; "
                    f"JSON `{record.get('json')}`, Markdown `{record.get('markdown')}`"
                )
                for label, record in lockin_audits.items()
            ],
            *([] if lockin_audits else ["- none"]),
            "",
            "## Guarded Chunk Acquisition Template",
            "",
            "Run the printed chunk-plan sequence for each recipe. Keep the accepted previous run and hardware approval note specific to the lab state.",
            "",
            "```powershell",
            *[
                (
                    f"ptm dual-gate-lockin {path} --allow-active-sweep --stop-after-new-points {chunk_size} "
                    f"--max-hardware-points {max_hardware_points} --hardware-approval-note \"<lab note>\" "
                    f"--accepted-previous-run {accepted} --progress --plot --report --gate-stats"
                )
                for _, _, path, _ in copied_suite
            ],
            "```",
            "",
            "## Feedback And Adjustment Loop",
            "",
            "```powershell",
            "ptm dual-gate-lockin-chunk-feedback data\\raw\\<chunk_01_run> data\\raw\\<chunk_02_run> --output docs\\<sample>_chunk_feedback.md",
            f"ptm dual-gate-lockin-hall-suite-adjust-recipes {copied_recipes['longitudinal']} {copied_recipes['plus']} {copied_recipes['minus']} configs\\recipes\\<adjusted_suite> --gate-nplc <NPLC> --gate-settle-s <seconds> --lockin-sensitivity-index <index> --lockin-time-constant-index <index>{zero_arg}",
            "```",
            "",
            "## Stitch And Hall Analysis",
            "",
            "```powershell",
            *[
                (
                    f"ptm dual-gate-lockin-stitch-chunks data\\raw\\<{recipe.measurement_name}_chunk_01> "
                    f"data\\raw\\<{recipe.measurement_name}_chunk_02> --measurement-name {recipe.measurement_name}_stitched "
                    "--gate-stats --plot --report"
                )
                for _, _, _, recipe in copied_suite
            ],
            f"ptm dual-gate-lockin-hall-antisym data\\raw\\<{recipes['plus'].measurement_name}_stitched> data\\raw\\<{recipes['minus'].measurement_name}_stitched> --output-dir data\\analysis\\<hall_antisym_folder>",
            *(
                [
                    f"ptm dual-gate-lockin-hall-zero-correct data\\raw\\<{recipes['plus'].measurement_name}_stitched> data\\raw\\<{recipes['zero'].measurement_name}_stitched> --output-dir data\\analysis\\<hall_zero_corrected_folder>"
                ]
                if "zero" in recipes
                else []
            ),
            f"ptm dual-gate-lockin-hall-mobility data\\analysis\\<hall_density_folder> data\\raw\\<{recipes['longitudinal'].measurement_name}_stitched> --output-dir data\\analysis\\<hall_mobility_folder>",
            "```",
            "",
            "## Attached Lab Files",
            "",
            *(
                [f"- {record['kind']}: `{record['path']}`" for record in extras]
                if extras
                else ["- none"]
            ),
            "",
            "## Plan Snapshot",
            "",
            "```text",
            format_dual_gate_lockin_plan(recipes["longitudinal"], safety, copied_recipes["longitudinal"], preview_points=3),
            "```",
            "",
        ]
    )


def _format_hall_suite_package_prerequisites(prerequisites: dict[str, dict[str, Any]]) -> list[str]:
    smoke = prerequisites.get("four_terminal_ac_smoke_intake")
    if not smoke:
        return [
            "- Four-terminal AC smoke intake: not attached",
            "- Before graphene Hall scans, attach a PASS `ptm ac-lockin-lab-smoke-intake --json-output` artifact when available.",
        ]
    excitation = ", ".join(str(contact) for contact in smoke.get("topology_excitation_contacts") or []) or "n/a"
    voltage = ", ".join(str(contact) for contact in smoke.get("topology_lockin_input_contacts") or []) or "n/a"
    return [
        "- Four-terminal AC smoke intake: PASS",
        f"- Intake JSON: `{smoke.get('path')}`",
        f"- Approval note: {smoke.get('hardware_guard_approval_note') or 'n/a'}",
        f"- Point guard: {smoke.get('hardware_guard_point_count')} <= {smoke.get('hardware_guard_max_points')}",
        f"- SR860 voltage input: {smoke.get('lockin_voltage_input') or 'n/a'}",
        f"- Excitation contacts: {excitation}",
        f"- SR860 voltage contacts: {voltage}",
        f"- Source NPLC: {smoke.get('source_nplc')}",
    ]


def format_dual_gate_lockin_hall_suite_adjustment_review(
    input_audit: HallSuiteAudit,
    output_audit: HallSuiteAudit,
    safety: SafetyPreset,
    *,
    adjustment_note: str | None = None,
) -> str:
    recipes = _load_suite_recipes(output_audit)
    suite = _suite_entries(output_audit, recipes)
    zero_arg = f" --zero-field-recipe {output_audit.zero_hall_recipe}" if output_audit.zero_hall_recipe else ""
    return "\n".join(
        [
            "# Dual-Gate Lock-In Hall Suite Adjustment Review",
            "",
            "## Input Suite",
            "",
            format_hall_suite_audit(input_audit),
            "",
            "## Adjusted Suite",
            "",
            format_hall_suite_audit(output_audit),
            "",
            f"- Adjustment note: {adjustment_note or 'n/a'}",
            "",
            "## Adjusted Measurement Parameters",
            "",
            "| Role | Recipe | Gate1 NPLC | Gate2 NPLC | Gate1 settle (s) | Gate2 settle (s) | SR860 sensitivity | SR860 tau | SR860 read settle (s) |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
            *[
                _suite_adjustment_parameter_row(label, path, recipe)
                for _, label, path, recipe in suite
            ],
            "",
            "## Required Checks Before Hardware",
            "",
            "```powershell",
            (
                f"ptm dual-gate-lockin-hall-suite-check {output_audit.longitudinal_recipe} "
                f"{output_audit.plus_hall_recipe} {output_audit.minus_hall_recipe}{zero_arg}"
            ),
            (
                f"ptm dual-gate-lockin-hall-suite-plan {output_audit.longitudinal_recipe} "
                f"{output_audit.plus_hall_recipe} {output_audit.minus_hall_recipe}{zero_arg}"
            ),
            (
                f"ptm dual-gate-lockin-hall-suite-chunk-plan {output_audit.longitudinal_recipe} "
                f"{output_audit.plus_hall_recipe} {output_audit.minus_hall_recipe} --chunk-size <N>{zero_arg}"
            ),
            *[f"ptm dual-gate-lockin-preflight {path}" for _, _, path, _ in suite],
            "```",
            "",
            "## Plan Snapshots",
            "",
            *[
                "\n".join(
                    [
                        f"### {label}",
                        "",
                        "```text",
                        format_dual_gate_lockin_plan(recipe, safety, path, preview_points=3),
                        "```",
                        "",
                    ]
                )
                for _, label, path, recipe in suite
            ],
        ]
    )


def format_hall_suite_review(
    base_recipe_path: str | Path,
    longitudinal_recipe: str | Path,
    plus_hall_recipe: str | Path,
    minus_hall_recipe: str | Path,
    zero_hall_recipe: str | Path | None,
    longitudinal_data: dict[str, Any],
    plus_data: dict[str, Any],
    safety: SafetyPreset,
) -> str:
    longitudinal_model = DualGateLockInRecipe.model_validate(longitudinal_data)
    plus_model = DualGateLockInRecipe.model_validate(plus_data)
    zero_line = f"- Zero-field Vxy: `{zero_hall_recipe}`" if zero_hall_recipe is not None else "- Zero-field Vxy: not generated"
    zero_analysis = (
        "ptm dual-gate-lockin-hall-zero-correct data\\raw\\<plus_B_run> data\\raw\\<zero_B_run> --output-dir data\\analysis\\<hall_zero_corrected_folder>"
        if zero_hall_recipe is not None
        else "# zero-field correction not generated for this suite"
    )
    return "\n".join(
        [
            "# Dual-Gate Lock-In Hall Suite Review",
            "",
            f"- Base recipe: `{base_recipe_path}`",
            f"- Longitudinal Vxx: `{longitudinal_recipe}`",
            f"- Positive-field Vxy: `{plus_hall_recipe}`",
            f"- Negative-field Vxy: `{minus_hall_recipe}`",
            zero_line,
            f"- Gate-grid points per recipe: {dual_gate_lockin_point_count(longitudinal_model)}",
            "",
            "## Hardware-Free Checks",
            "",
            "```powershell",
            f"ptm dual-gate-lockin-hall-suite-check {longitudinal_recipe} {plus_hall_recipe} {minus_hall_recipe}"
            + (f" --zero-field-recipe {zero_hall_recipe}" if zero_hall_recipe is not None else ""),
            f"ptm dual-gate-lockin-hall-suite-plan {longitudinal_recipe} {plus_hall_recipe} {minus_hall_recipe}"
            + (f" --zero-field-recipe {zero_hall_recipe}" if zero_hall_recipe is not None else ""),
            f"ptm dual-gate-lockin-hall-suite-chunk-plan {longitudinal_recipe} {plus_hall_recipe} {minus_hall_recipe} --chunk-size <N>"
            + (f" --zero-field-recipe {zero_hall_recipe}" if zero_hall_recipe is not None else ""),
            f"ptm dual-gate-lockin-plan {longitudinal_recipe}",
            f"ptm dual-gate-lockin-plan {plus_hall_recipe}",
            f"ptm dual-gate-lockin-plan {minus_hall_recipe}",
            *( [f"ptm dual-gate-lockin-plan {zero_hall_recipe}"] if zero_hall_recipe is not None else [] ),
            f"ptm dual-gate-lockin-preflight {longitudinal_recipe}",
            f"ptm dual-gate-lockin-preflight {plus_hall_recipe}",
            f"ptm dual-gate-lockin-preflight {minus_hall_recipe}",
            *( [f"ptm dual-gate-lockin-preflight {zero_hall_recipe}"] if zero_hall_recipe is not None else [] ),
            "```",
            "",
            "## Hardware Run Templates",
            "",
            "Use accepted previous-run guards and point limits appropriate for the lab state.",
            "",
            "```powershell",
            f"ptm dual-gate-lockin {longitudinal_recipe} --allow-active-sweep --max-hardware-points <N> --hardware-approval-note \"<lab note>\" --accepted-previous-run data\\raw\\<accepted_run> --progress --plot --report --gate-stats",
            f"ptm dual-gate-lockin {plus_hall_recipe} --allow-active-sweep --max-hardware-points <N> --hardware-approval-note \"<lab note>\" --accepted-previous-run data\\raw\\<accepted_run> --progress --plot --report --gate-stats",
            f"ptm dual-gate-lockin {minus_hall_recipe} --allow-active-sweep --max-hardware-points <N> --hardware-approval-note \"<lab note>\" --accepted-previous-run data\\raw\\<accepted_run> --progress --plot --report --gate-stats",
            *( [f"ptm dual-gate-lockin {zero_hall_recipe} --allow-active-sweep --max-hardware-points <N> --hardware-approval-note \"<lab note>\" --accepted-previous-run data\\raw\\<accepted_run> --progress --plot --report --gate-stats"] if zero_hall_recipe is not None else [] ),
            "```",
            "",
            "## Analysis Commands",
            "",
            "```powershell",
            "ptm dual-gate-lockin-hall-antisym data\\raw\\<plus_B_run> data\\raw\\<minus_B_run> --output-dir data\\analysis\\<hall_antisym_folder>",
            zero_analysis,
            "ptm dual-gate-lockin-hall-mobility data\\analysis\\<hall_density_folder> data\\raw\\<longitudinal_Vxx_run> --output-dir data\\analysis\\<hall_mobility_folder>",
            "```",
            "",
            "## Longitudinal Plan Snapshot",
            "",
            "```text",
            format_dual_gate_lockin_plan(longitudinal_model, safety, longitudinal_recipe, preview_points=3),
            "```",
            "",
            "## Hall Plan Snapshot",
            "",
            "```text",
            format_dual_gate_lockin_plan(plus_model, safety, plus_hall_recipe, preview_points=3),
            "```",
            "",
        ]
    )


def audit_dual_gate_lockin_hall_suite(
    longitudinal_recipe: str | Path,
    plus_hall_recipe: str | Path,
    minus_hall_recipe: str | Path,
    zero_hall_recipe: str | Path | None = None,
) -> HallSuiteAudit:
    longitudinal_path = Path(longitudinal_recipe)
    plus_path = Path(plus_hall_recipe)
    minus_path = Path(minus_hall_recipe)
    zero_path = Path(zero_hall_recipe) if zero_hall_recipe is not None else None
    recipes: dict[str, DualGateLockInRecipe] = {}
    issues: list[HallSuiteIssue] = []
    for label, path in [
        ("longitudinal", longitudinal_path),
        ("plus", plus_path),
        ("minus", minus_path),
        *([("zero", zero_path)] if zero_path is not None else []),
    ]:
        try:
            recipes[label] = DualGateLockInRecipe.model_validate(load_yaml(path))
        except Exception as exc:
            issues.append(HallSuiteIssue("error", f"{label}_recipe", f"{type(exc).__name__}: {exc}"))
    if issues:
        return HallSuiteAudit(longitudinal_path, plus_path, minus_path, zero_path, False, None, tuple(issues))

    longitudinal = recipes["longitudinal"]
    plus = recipes["plus"]
    minus = recipes["minus"]
    zero = recipes.get("zero")
    _check_role("longitudinal", longitudinal, "longitudinal", issues)
    _check_role("plus", plus, "hall", issues)
    _check_role("minus", minus, "hall", issues)
    if zero is not None:
        _check_role("zero", zero, "hall", issues)
    _check_magnetic_fields(plus, minus, zero, issues)
    _check_longitudinal_geometry(longitudinal, issues)
    for label, recipe in [("plus", plus), ("minus", minus), *([("zero", zero)] if zero is not None else [])]:
        _check_hall_geometry(label, recipe, issues)

    for section in ["measurement_geometry", "gate1_instrument", "gate2_instrument", "lockin", "gate1_sweep", "gate2_sweep"]:
        reference = getattr(longitudinal, section).model_dump(mode="json")
        for label, recipe in [("plus", plus), ("minus", minus), *([("zero", zero)] if zero is not None else [])]:
            candidate = getattr(recipe, section).model_dump(mode="json")
            if candidate != reference:
                issues.append(HallSuiteIssue("error", section, f"{label} recipe differs from longitudinal recipe"))
    for label, recipe in [("plus", plus), ("minus", minus), *([("zero", zero)] if zero is not None else [])]:
        if recipe.safety_preset != longitudinal.safety_preset:
            issues.append(HallSuiteIssue("error", "safety_preset", f"{label} recipe safety_preset differs"))
        _compare_topology_shared_fields(label, longitudinal, recipe, issues)

    point_count = dual_gate_lockin_point_count(longitudinal)
    for label, recipe in [("plus", plus), ("minus", minus), *([("zero", zero)] if zero is not None else [])]:
        candidate_points = dual_gate_lockin_point_count(recipe)
        if candidate_points != point_count:
            issues.append(HallSuiteIssue("error", "point_count", f"{label} recipe has {candidate_points} points, expected {point_count}"))
    if longitudinal.topology.lockin_input_contacts == plus.topology.lockin_input_contacts:
        issues.append(
            HallSuiteIssue(
                "warning",
                "voltage_contacts",
                "longitudinal and Hall recipes use the same lock-in voltage contacts; confirm this is intentional",
            )
        )
    errors = [issue for issue in issues if issue.severity == "error"]
    return HallSuiteAudit(longitudinal_path, plus_path, minus_path, zero_path, not errors, point_count, tuple(issues))


def format_hall_suite_audit(audit: HallSuiteAudit) -> str:
    status = "PASS" if audit.compatible else "FAIL"
    lines = [
        f"Dual-gate lock-in Hall suite consistency: {status}",
        f"Longitudinal recipe: {audit.longitudinal_recipe}",
        f"Positive-field Hall recipe: {audit.plus_hall_recipe}",
        f"Negative-field Hall recipe: {audit.minus_hall_recipe}",
        f"Zero-field Hall recipe: {audit.zero_hall_recipe if audit.zero_hall_recipe is not None else 'not supplied'}",
        f"Point count: {audit.point_count if audit.point_count is not None else 'n/a'}",
    ]
    if audit.issues:
        lines.append("Issues:")
        for issue in audit.issues:
            lines.append(f"- [{issue.severity}] {issue.check}: {issue.message}")
    else:
        lines.append("Issues: none")
    return "\n".join(lines)


def format_dual_gate_lockin_hall_suite_plan(
    longitudinal_recipe: str | Path,
    plus_hall_recipe: str | Path,
    minus_hall_recipe: str | Path,
    zero_hall_recipe: str | Path | None = None,
    *,
    safety_dir: str | Path = "configs/safety",
    preview_points: int = 3,
) -> str:
    audit = audit_dual_gate_lockin_hall_suite(
        longitudinal_recipe,
        plus_hall_recipe,
        minus_hall_recipe,
        zero_hall_recipe=zero_hall_recipe,
    )
    lines = [
        "Dual-Gate Lock-In Hall Suite Plan",
        "",
        format_hall_suite_audit(audit),
        "",
    ]
    if not audit.compatible:
        lines.extend(
            [
                "Suite plan stopped because consistency check failed.",
                "Fix the listed issue(s) before preflight or hardware use.",
                "",
            ]
        )
        return "\n".join(lines)

    longitudinal = DualGateLockInRecipe.model_validate(load_yaml(audit.longitudinal_recipe))
    plus = DualGateLockInRecipe.model_validate(load_yaml(audit.plus_hall_recipe))
    minus = DualGateLockInRecipe.model_validate(load_yaml(audit.minus_hall_recipe))
    zero = DualGateLockInRecipe.model_validate(load_yaml(audit.zero_hall_recipe)) if audit.zero_hall_recipe else None
    safety = load_named_safety_preset(longitudinal.safety_preset, safety_dir)
    suite = [
        ("1", "Longitudinal Vxx", audit.longitudinal_recipe, longitudinal),
        ("2", "+B Hall Vxy", audit.plus_hall_recipe, plus),
        ("3", "-B Hall Vxy", audit.minus_hall_recipe, minus),
    ]
    if zero is not None and audit.zero_hall_recipe is not None:
        suite.append(("4", "0B Hall Vxy", audit.zero_hall_recipe, zero))

    lines.extend(
        [
            "Measurement Order",
            "",
            *[
                (
                    f"{index}. {label}: `{path}` "
                    f"(role={recipe.topology.voltage_probe_role}, B={_fmt_field(recipe.topology.magnetic_field_t)}, "
                    f"contacts={', '.join(recipe.topology.lockin_input_contacts)})"
                )
                for index, label, path, recipe in suite
            ],
            "",
            "Hardware-Free Gate Commands",
            "",
            "```powershell",
            f"ptm dual-gate-lockin-hall-suite-check {audit.longitudinal_recipe} {audit.plus_hall_recipe} {audit.minus_hall_recipe}"
            + (f" --zero-field-recipe {audit.zero_hall_recipe}" if audit.zero_hall_recipe is not None else ""),
            *[f"ptm dual-gate-lockin-plan {path}" for _, _, path, _ in suite],
            *[f"ptm dual-gate-lockin-chunk-plan {path} --chunk-size <N>" for _, _, path, _ in suite],
            *[f"ptm dual-gate-lockin-preflight {path}" for _, _, path, _ in suite],
            *[f"ptm dual-gate-lockin-resume-check {path} data\\raw\\<partial_{recipe.measurement_name}_run>" for _, _, path, recipe in suite],
            "```",
            "",
            "Guarded Hardware Run Templates",
            "",
            "```powershell",
            *[
                (
                    f"ptm dual-gate-lockin {path} --allow-active-sweep --max-hardware-points <N> "
                    f"--hardware-approval-note \"<lab note>\" --accepted-previous-run data\\raw\\<accepted_run> "
                    "--progress --plot --report --gate-stats"
                )
                for _, _, path, _ in suite
            ],
            "```",
            "",
            "Analysis Commands",
            "",
            "```powershell",
            f"ptm dual-gate-lockin-hall-antisym data\\raw\\<{plus.measurement_name}_run> data\\raw\\<{minus.measurement_name}_run> --output-dir data\\analysis\\<hall_antisym_folder>",
            *(
                [
                    f"ptm dual-gate-lockin-hall-zero-correct data\\raw\\<{plus.measurement_name}_run> data\\raw\\<{zero.measurement_name}_run> --output-dir data\\analysis\\<hall_zero_corrected_folder>"
                ]
                if zero is not None
                else []
            ),
            f"ptm dual-gate-lockin-hall-mobility data\\analysis\\<hall_density_folder> data\\raw\\<{longitudinal.measurement_name}_run> --output-dir data\\analysis\\<hall_mobility_folder>",
            "```",
            "",
            "Plan Snapshots",
            "",
        ]
    )
    for _, label, path, recipe in suite:
        lines.extend(
            [
                f"### {label}",
                "",
                "```text",
                format_dual_gate_lockin_plan(recipe, safety, path, preview_points=preview_points),
                "```",
                "",
            ]
        )
    return "\n".join(lines)


def format_dual_gate_lockin_hall_suite_chunk_workflow_plan(
    longitudinal_recipe: str | Path,
    plus_hall_recipe: str | Path,
    minus_hall_recipe: str | Path,
    zero_hall_recipe: str | Path | None = None,
    *,
    chunk_size: int,
    max_hardware_points: int = 9,
) -> str:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if max_hardware_points <= 0:
        raise ValueError("max_hardware_points must be positive")
    audit = audit_dual_gate_lockin_hall_suite(
        longitudinal_recipe,
        plus_hall_recipe,
        minus_hall_recipe,
        zero_hall_recipe=zero_hall_recipe,
    )
    lines = [
        "Dual-Gate Lock-In Hall Suite Chunk Workflow",
        "",
        format_hall_suite_audit(audit),
        "",
    ]
    if not audit.compatible:
        lines.extend(
            [
                "Chunk workflow stopped because consistency check failed.",
                "Fix the listed issue(s) before planning chunked hardware use.",
                "",
            ]
        )
        return "\n".join(lines)

    recipes = _load_suite_recipes(audit)
    suite = _suite_entries(audit, recipes)
    chunks_per_recipe = (
        0 if audit.point_count is None else (audit.point_count + chunk_size - 1) // chunk_size
    )
    lines.extend(
        [
            f"Chunk size: {chunk_size}",
            f"Max hardware points per invocation: {max_hardware_points}",
            f"Gate-grid points per recipe: {audit.point_count if audit.point_count is not None else 'n/a'}",
            f"Chunks per recipe: {chunks_per_recipe}",
            "",
            "Hardware-Free Planning Commands",
            "",
            "```powershell",
            f"ptm dual-gate-lockin-hall-suite-check {audit.longitudinal_recipe} {audit.plus_hall_recipe} {audit.minus_hall_recipe}"
            + (f" --zero-field-recipe {audit.zero_hall_recipe}" if audit.zero_hall_recipe is not None else ""),
            *[
                f"ptm dual-gate-lockin-chunk-plan {path} --chunk-size {chunk_size} --max-hardware-points {max_hardware_points}"
                for _, _, path, _ in suite
            ],
            "```",
            "",
            "Per-Recipe Chunk Acquisition",
            "",
        ]
    )
    for _, label, path, recipe in suite:
        lines.extend(
            [
                f"### {label}",
                "",
                "```powershell",
                f"ptm dual-gate-lockin-chunk-plan {path} --chunk-size {chunk_size} --max-hardware-points {max_hardware_points}",
                (
                    f"# Run the printed chunk sequence for {recipe.measurement_name}, "
                    "reviewing each checkpoint before continuing."
                ),
                "```",
                "",
            ]
        )
    lines.extend(
        [
            "Stitch Completed Chunks",
            "",
            "```powershell",
            *[
                (
                    f"ptm dual-gate-lockin-stitch-chunks data\\raw\\<{recipe.measurement_name}_chunk_01> "
                    f"data\\raw\\<{recipe.measurement_name}_chunk_02> --measurement-name {recipe.measurement_name}_stitched "
                    "--gate-stats --plot --report"
                )
                for _, _, _, recipe in suite
            ],
            "```",
            "",
            "Hall Analysis From Stitched Runs",
            "",
            "```powershell",
            f"ptm dual-gate-lockin-hall-antisym data\\raw\\<{recipes['plus'].measurement_name}_stitched> data\\raw\\<{recipes['minus'].measurement_name}_stitched> --output-dir data\\analysis\\<hall_antisym_folder>",
            *(
                [
                    f"ptm dual-gate-lockin-hall-zero-correct data\\raw\\<{recipes['plus'].measurement_name}_stitched> data\\raw\\<{recipes['zero'].measurement_name}_stitched> --output-dir data\\analysis\\<hall_zero_corrected_folder>"
                ]
                if "zero" in recipes
                else []
            ),
            f"ptm dual-gate-lockin-hall-mobility data\\analysis\\<hall_density_folder> data\\raw\\<{recipes['longitudinal'].measurement_name}_stitched> --output-dir data\\analysis\\<hall_mobility_folder>",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def _load_suite_recipes(audit: HallSuiteAudit) -> dict[str, DualGateLockInRecipe]:
    recipes = {
        "longitudinal": DualGateLockInRecipe.model_validate(load_yaml(audit.longitudinal_recipe)),
        "plus": DualGateLockInRecipe.model_validate(load_yaml(audit.plus_hall_recipe)),
        "minus": DualGateLockInRecipe.model_validate(load_yaml(audit.minus_hall_recipe)),
    }
    if audit.zero_hall_recipe is not None:
        recipes["zero"] = DualGateLockInRecipe.model_validate(load_yaml(audit.zero_hall_recipe))
    return recipes


def _suite_entries(
    audit: HallSuiteAudit,
    recipes: dict[str, DualGateLockInRecipe],
) -> list[tuple[str, str, Path, DualGateLockInRecipe]]:
    entries = [
        ("1", "Longitudinal Vxx", audit.longitudinal_recipe, recipes["longitudinal"]),
        ("2", "+B Hall Vxy", audit.plus_hall_recipe, recipes["plus"]),
        ("3", "-B Hall Vxy", audit.minus_hall_recipe, recipes["minus"]),
    ]
    if audit.zero_hall_recipe is not None and "zero" in recipes:
        entries.append(("4", "0B Hall Vxy", audit.zero_hall_recipe, recipes["zero"]))
    return entries


def _suite_key_entries(
    audit: HallSuiteAudit,
    recipes: dict[str, DualGateLockInRecipe],
) -> list[tuple[str, str, Path, DualGateLockInRecipe]]:
    entries = [
        ("longitudinal", "Longitudinal Vxx", audit.longitudinal_recipe, recipes["longitudinal"]),
        ("plus", "+B Hall Vxy", audit.plus_hall_recipe, recipes["plus"]),
        ("minus", "-B Hall Vxy", audit.minus_hall_recipe, recipes["minus"]),
    ]
    if audit.zero_hall_recipe is not None and "zero" in recipes:
        entries.append(("zero", "0B Hall Vxy", audit.zero_hall_recipe, recipes["zero"]))
    return entries


def _suite_adjusted_measurement_name(prefix: str, recipe: DualGateLockInRecipe) -> str:
    role = recipe.topology.voltage_probe_role
    field = recipe.topology.magnetic_field_t
    if role == "longitudinal":
        return f"{prefix}_vxx"
    if field is None or abs(field) <= 1e-12:
        return f"{prefix}_vxy_zero_b"
    if field > 0:
        return f"{prefix}_vxy_plus_b"
    return f"{prefix}_vxy_minus_b"


def _suite_adjustment_parameter_row(
    label: str,
    path: Path,
    recipe: DualGateLockInRecipe,
) -> str:
    return (
        f"| {label} | `{path}` | "
        f"{_fmt_optional(recipe.gate1_instrument.nplc)} | "
        f"{_fmt_optional(recipe.gate2_instrument.nplc)} | "
        f"{_fmt_optional(recipe.gate1_sweep.settle_s)} | "
        f"{_fmt_optional(recipe.gate2_sweep.settle_s)} | "
        f"{_fmt_optional(recipe.lockin.sensitivity_index)} | "
        f"{_fmt_optional(recipe.lockin.time_constant_index)} | "
        f"{_fmt_optional(recipe.lockin.read_settle_s)} |"
    )


def _copy_suite_recipes(audit: HallSuiteAudit, recipes_dir: Path) -> dict[str, Path]:
    paths = {
        "longitudinal": audit.longitudinal_recipe,
        "plus": audit.plus_hall_recipe,
        "minus": audit.minus_hall_recipe,
    }
    if audit.zero_hall_recipe is not None:
        paths["zero"] = audit.zero_hall_recipe
    copied = {}
    for key, source in paths.items():
        target = recipes_dir / source.name
        shutil.copy2(source, target)
        copied[key] = target
    return copied


def _write_hall_suite_keithley_audits(copied_recipes: dict[str, Path], package_dir: Path) -> dict[str, dict[str, Any]]:
    audit_dir = package_dir / "keithley_audit"
    audit_dir.mkdir()
    records: dict[str, dict[str, Any]] = {}
    for key, recipe_path in copied_recipes.items():
        recipe = DualGateLockInRecipe.model_validate(load_yaml(recipe_path))
        audits = audit_smu_hardware_parameters(recipe)
        payload = {
            "recipe_key": key,
            "recipe_path": recipe_path.relative_to(package_dir).as_posix(),
            **smu_hardware_parameter_audit_to_dict(audits),
        }
        json_path = audit_dir / f"{key}_keithley_audit.json"
        markdown_path = audit_dir / f"{key}_keithley_audit.md"
        json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        markdown_path.write_text(
            "\n".join(
                [
                    f"# {_suite_key_label(key)} Keithley Parameter Audit",
                    "",
                    f"- Recipe: `{payload['recipe_path']}`",
                    f"- Hardware-ready: {payload['ok_for_hardware']}",
                    "",
                    format_smu_hardware_parameter_audit(audits),
                    "",
                ]
            ),
            encoding="utf-8",
        )
        records[key] = {
            "json": json_path.relative_to(package_dir).as_posix(),
            "markdown": markdown_path.relative_to(package_dir).as_posix(),
            "ok_for_hardware": bool(payload["ok_for_hardware"]),
            "missing_roles": [
                {"role": role["role"], "missing_required_parameters": role["missing_required_parameters"]}
                for role in payload["roles"]
                if role["missing_required_parameters"]
            ],
        }
    return records


def _write_hall_suite_lockin_audits(copied_recipes: dict[str, Path], package_dir: Path) -> dict[str, dict[str, Any]]:
    audit_dir = package_dir / "lockin_audit"
    audit_dir.mkdir()
    records: dict[str, dict[str, Any]] = {}
    for key, recipe_path in copied_recipes.items():
        recipe = DualGateLockInRecipe.model_validate(load_yaml(recipe_path))
        payload = _lockin_setting_audit_payload(key, recipe_path.relative_to(package_dir).as_posix(), recipe)
        json_path = audit_dir / f"{key}_sr860_audit.json"
        markdown_path = audit_dir / f"{key}_sr860_audit.md"
        json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        markdown_path.write_text(_format_lockin_setting_audit_markdown(payload), encoding="utf-8")
        records[key] = {
            "json": json_path.relative_to(package_dir).as_posix(),
            "markdown": markdown_path.relative_to(package_dir).as_posix(),
            "ok_for_hardware": bool(payload["ok_for_hardware"]),
            "declared_expected_setting_count": len(payload["expected_settings"]),
            "read_settle_s": payload["read_settle_s"],
            "missing_required_parameters": payload["missing_required_parameters"],
            "settle_policy_ok": payload["settle_policy_ok"],
        }
    return records


def _measurement_condition_audits_manifest(
    keithley_audits: dict[str, dict[str, Any]],
    lockin_audits: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    for instrument, audit_type, source in [
        ("keithley_2450", "smu_hardware_parameters", keithley_audits),
        ("srs_sr860", "lockin_hardware_parameters", lockin_audits),
    ]:
        for recipe_key, record in source.items():
            records.append(
                {
                    "recipe_key": recipe_key,
                    "instrument": instrument,
                    "audit_type": audit_type,
                    "json": record.get("json"),
                    "markdown": record.get("markdown"),
                    "ok_for_hardware": bool(record.get("ok_for_hardware")),
                    "summary": _measurement_condition_audit_summary(record),
                }
            )
    return {
        "schema_version": 1,
        "ok_for_hardware": all(record["ok_for_hardware"] for record in records),
        "records": records,
    }


def _measurement_condition_audit_summary(record: dict[str, Any]) -> dict[str, Any]:
    summary_keys = [
        "missing_roles",
        "declared_expected_setting_count",
        "read_settle_s",
        "missing_required_parameters",
        "settle_policy_ok",
    ]
    return {key: record[key] for key in summary_keys if key in record}


def _lockin_setting_audit_payload(key: str, recipe_path: str, recipe: DualGateLockInRecipe) -> dict[str, Any]:
    lockin = recipe.lockin.model_dump(mode="json")
    expected = expected_lockin_settings(lockin)
    hardware_audits = audit_lockin_hardware_parameters(recipe)
    hardware_payload = lockin_hardware_parameter_audit_to_dict(hardware_audits)
    missing_required_parameters = [
        parameter
        for role in hardware_payload["roles"]
        for parameter in role["missing_required_parameters"]
    ]
    settle_policy_ok = all(bool(role["settle_policy_ok"]) for role in hardware_payload["roles"])
    return {
        "recipe_key": key,
        "recipe_path": recipe_path,
        "lockin_id": recipe.lockin.id,
        "address": recipe.lockin.address,
        "enabled": recipe.lockin.enabled,
        "channels": recipe.lockin.channels,
        "read_timing": recipe.lockin.read_timing,
        "expected_settings": expected,
        "expected_setting_count": len(expected),
        "time_constant_s": lockin_time_constant_s(lockin),
        "settle_time_constants": recipe.lockin.settle_time_constants,
        "read_settle_s": lockin_read_settle_s(lockin),
        "hardware_parameter_audit": hardware_payload,
        "missing_required_parameters": missing_required_parameters,
        "settle_policy_ok": settle_policy_ok,
        "missing_review_fields": missing_required_parameters,
        "ok_for_hardware": recipe.lockin.enabled and bool(hardware_payload["ok_for_hardware"]),
    }


def _format_lockin_setting_audit_markdown(payload: dict[str, Any]) -> str:
    expected = payload.get("expected_settings") or {}
    lines = [
        f"# {_suite_key_label(str(payload['recipe_key']))} SR860 Setting Audit",
        "",
        f"- Recipe: `{payload['recipe_path']}`",
        f"- Lock-in: {payload['lockin_id']} @ `{payload['address']}`",
        f"- Enabled: {payload['enabled']}",
        f"- Channels: {', '.join(payload.get('channels') or [])}",
        f"- Read timing: {payload['read_timing']}",
        f"- Time constant: {_fmt_optional(payload.get('time_constant_s'))} s",
        f"- Read settle: {_fmt_optional(payload.get('read_settle_s'))} s",
        f"- Hardware-ready: {payload['ok_for_hardware']}",
        f"- Settle policy OK: {payload.get('settle_policy_ok')}",
        "",
        "## Expected SR860 Settings",
        "",
    ]
    if expected:
        lines.extend(f"- {key}: {value}" for key, value in expected.items())
    else:
        lines.append("- none declared")
    missing = payload.get("missing_required_parameters") or payload.get("missing_review_fields") or []
    lines.extend(["", "## Required Hardware Parameters", ""])
    if missing:
        lines.append(f"- Missing required parameters: {', '.join(missing)}")
    else:
        lines.append("- all required SR860 hardware parameters are declared")
    lines.extend(
        [
            "",
            "## Hardware Parameter Audit",
            "",
            *_format_lockin_hardware_parameter_audit_payload(payload.get("hardware_parameter_audit") or {}),
            "",
        ]
    )
    return "\n".join(lines)


def _format_lockin_hardware_parameter_audit_payload(payload: dict[str, Any]) -> list[str]:
    roles = payload.get("roles") if isinstance(payload.get("roles"), list) else []
    lines = [
        f"Hardware-ready: {payload.get('ok_for_hardware')}",
        "",
        "| Role | Instrument | Address | Ref | Freq (Hz) | Sine (V) | Input | Vin | Range (V) | Sens idx | TC idx | Settle TC | Read settle (s) | Slope | Sync | Status |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    if not roles:
        lines.append("| n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | NO LOCK-IN |")
        return lines
    for role in roles:
        if not isinstance(role, dict):
            continue
        status_items = []
        missing = role.get("missing_required_parameters") if isinstance(role.get("missing_required_parameters"), list) else []
        if missing:
            status_items.append("MISSING " + ", ".join(str(item) for item in missing))
        if role.get("settle_policy_ok") is not True:
            status_items.append("MISSING positive settle policy")
        status = "PASS" if not status_items else "; ".join(status_items)
        lines.append(
            "| "
            + " | ".join(
                [
                    str(role.get("role") or "n/a"),
                    str(role.get("instrument_id") or "n/a"),
                    f"`{role.get('address')}`" if role.get("address") else "n/a",
                    str(role.get("reference_source") or "auto"),
                    _fmt_optional(role.get("reference_frequency_hz")),
                    _fmt_optional(role.get("sine_output_amplitude_v")),
                    str(role.get("input_mode") or "auto"),
                    str(role.get("voltage_input") or "auto"),
                    _fmt_optional(role.get("voltage_input_range_v")),
                    _fmt_optional(role.get("sensitivity_index")),
                    _fmt_optional(role.get("time_constant_index")),
                    _fmt_optional(role.get("settle_time_constants")),
                    _fmt_optional(role.get("read_settle_s")),
                    _fmt_optional(role.get("filter_slope_db_per_oct")),
                    "auto" if role.get("synchronous_filter") is None else str(role.get("synchronous_filter")),
                    status,
                ]
            )
            + " |"
        )
    return lines


def _resolve_package_manifest_path(package_manifest_or_dir: str | Path) -> Path:
    path = Path(package_manifest_or_dir)
    if path.is_dir():
        path = path / "package_manifest.json"
    if not path.exists():
        raise FileNotFoundError(f"Package manifest does not exist: {path}")
    return path


def _resolve_result_intake_json_path(result_intake_json_or_package_dir: str | Path) -> Path:
    path = Path(result_intake_json_or_package_dir)
    if path.is_dir():
        path = path / "result_intake.json"
    if not path.exists():
        raise FileNotFoundError(f"Result intake JSON does not exist: {path}")
    return path


def _load_result_intake_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _resolve_analysis_review_json_path(review_json_or_analysis_dir: str | Path) -> Path:
    path = Path(review_json_or_analysis_dir)
    if path.is_dir():
        path = path / "hall_suite_analysis_review.json"
    if not path.exists():
        raise FileNotFoundError(f"Hall suite analysis review JSON does not exist: {path}")
    return path


def _resolve_next_scan_proposal_json_path(proposal_json_or_analysis_dir: str | Path) -> Path:
    path = Path(proposal_json_or_analysis_dir)
    if path.is_dir():
        path = path / "hall_suite_next_scan_proposal.json"
    if not path.exists():
        raise FileNotFoundError(f"Hall suite next-scan proposal JSON does not exist: {path}")
    return path


def _load_analysis_review_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _load_next_scan_proposal_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _proposal_package_manifest_path(proposal: dict[str, Any]) -> Path:
    settings = proposal.get("preserve_measurement_settings") if isinstance(proposal.get("preserve_measurement_settings"), dict) else {}
    source = settings.get("source")
    if not source or source == "not available":
        raise ValueError("proposal does not include a package manifest source for recipe generation")
    path = Path(str(source))
    if not path.exists():
        raise FileNotFoundError(f"Package manifest from proposal does not exist: {path}")
    return path


def _build_approved_next_scan_recipe_data(
    base_recipe_path: str | Path,
    *,
    measurement_name: str,
    proposed_gate_grid: dict[str, Any],
    approval_note: str,
    output_directory: str | Path | None,
) -> dict[str, Any]:
    data = dict(load_yaml(base_recipe_path))
    data["measurement_name"] = measurement_name
    if output_directory is not None:
        data["output"] = {**dict(data.get("output") or {}), "directory": str(output_directory)}
    _apply_proposed_gate_axis(data, "gate1_sweep", proposed_gate_grid.get("gate1"))
    _apply_proposed_gate_axis(data, "gate2_sweep", proposed_gate_grid.get("gate2"))
    experiment = dict(data.get("experiment") or {})
    existing_notes = str(experiment.get("notes") or "").strip()
    note = f"Approved next-scan proposal: {approval_note}"
    experiment["notes"] = f"{existing_notes}\n{note}".strip() if existing_notes else note
    data["experiment"] = experiment
    DualGateLockInRecipe.model_validate(data)
    return data


def _apply_proposed_gate_axis(data: dict[str, Any], sweep_key: str, proposed_axis: Any) -> None:
    if not isinstance(proposed_axis, dict):
        raise ValueError(f"proposal is missing {sweep_key} gate axis")
    start = _optional_float(proposed_axis.get("start_v"))
    stop = _optional_float(proposed_axis.get("stop_v"))
    points_value = proposed_axis.get("points")
    if start is None or stop is None or points_value is None:
        raise ValueError(f"proposal {sweep_key} axis must include start_v, stop_v, and points")
    try:
        points = int(points_value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"proposal {sweep_key} points must be an integer") from exc
    if points < 2:
        raise ValueError(f"proposal {sweep_key} points must be at least 2")
    data[sweep_key] = {**dict(data.get(sweep_key) or {}), "start_v": start, "stop_v": stop, "points": points}


def _read_required_csv(path: Path, expected_columns: list[str]) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Required CSV does not exist: {path}")
    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = [column for column in expected_columns if column not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"{path} is missing columns: {', '.join(missing)}")
        rows = [dict(row) for row in reader]
    if not rows:
        raise ValueError(f"{path} contains no rows")
    return rows


def _proposal_grid_summary(rows: list[dict[str, str]]) -> dict[str, dict[str, Any]]:
    return {
        "gate1": _proposal_axis_summary(_unique_floats(row.get("gate1_voltage_v") for row in rows)),
        "gate2": _proposal_axis_summary(_unique_floats(row.get("gate2_voltage_v") for row in rows)),
    }


def _proposal_axis_summary(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"start_v": None, "stop_v": None, "points": 0, "step_v": None, "span_v": None}
    diffs = [b - a for a, b in zip(values[:-1], values[1:]) if b != a]
    step = min(abs(diff) for diff in diffs) if diffs else None
    return {
        "start_v": values[0],
        "stop_v": values[-1],
        "points": len(values),
        "step_v": step,
        "span_v": values[-1] - values[0],
    }


def _unique_floats(values: Any) -> list[float]:
    parsed = {_optional_float(value) for value in values}
    return sorted(value for value in parsed if value is not None)


def _build_next_scan_gate_proposal(
    rows: list[dict[str, str]],
    grid: dict[str, dict[str, Any]],
    finite_density: list[float],
) -> dict[str, Any]:
    signs = {1 if value > 0 else -1 if value < 0 else 0 for value in finite_density}
    if not finite_density:
        return {
            "strategy": "repeat_or_debug_hall_signal",
            "rationale": "No finite Hall carrier density values were available; repeat a conservative checkpoint or inspect wiring/lock-in phase before broadening.",
            "gate_grid": _same_gate_grid(grid),
        }
    if 1 in signs and -1 in signs:
        low_density_rows = _lowest_abs_density_rows(rows)
        return {
            "strategy": "refine_charge_neutrality_region",
            "rationale": "Carrier density changes sign in the measured grid, so the next scan should refine around the lowest-density region while preserving measurement settings.",
            "gate_grid": {
                "gate1": _refined_axis_from_rows(low_density_rows, "gate1_voltage_v", grid.get("gate1", {})),
                "gate2": _refined_axis_from_rows(low_density_rows, "gate2_voltage_v", grid.get("gate2", {})),
            },
        }
    return {
        "strategy": "broaden_gate_window_after_single_density_sign",
        "rationale": "Carrier density kept one sign over the measured grid; the next candidate should modestly broaden both gate windows after lab approval.",
        "gate_grid": {
            "gate1": _broaden_axis(grid.get("gate1", {})),
            "gate2": _broaden_axis(grid.get("gate2", {})),
        },
    }


def _same_gate_grid(grid: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        axis: {
            "start_v": values.get("start_v"),
            "stop_v": values.get("stop_v"),
            "points": values.get("points"),
            "change": "repeat",
        }
        for axis, values in grid.items()
    }


def _lowest_abs_density_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    scored = []
    for row in rows:
        density = _optional_float(row.get("hall_carrier_density_per_m2"))
        if density is not None:
            scored.append((abs(density), row))
    if not scored:
        return rows
    scored.sort(key=lambda item: item[0])
    keep = max(2, min(len(scored), max(1, len(scored) // 4)))
    return [row for _, row in scored[:keep]]


def _refined_axis_from_rows(rows: list[dict[str, str]], column: str, current: dict[str, Any]) -> dict[str, Any]:
    values = _unique_floats(row.get(column) for row in rows)
    if not values:
        return _broaden_axis(current)
    step = _optional_float(current.get("step_v")) or 0.0
    current_start = _optional_float(current.get("start_v"))
    current_stop = _optional_float(current.get("stop_v"))
    start = min(values) - step
    stop = max(values) + step
    if current_start is not None:
        start = max(current_start, start)
    if current_stop is not None:
        stop = min(current_stop, stop)
    current_points = int(current.get("points") or 0)
    proposed_points = max(current_points, current_points * 2 - 1) if current_points else len(values)
    return {"start_v": start, "stop_v": stop, "points": proposed_points, "change": "refine"}


def _broaden_axis(current: dict[str, Any]) -> dict[str, Any]:
    start = _optional_float(current.get("start_v"))
    stop = _optional_float(current.get("stop_v"))
    points = int(current.get("points") or 0)
    if start is None or stop is None:
        return {"start_v": start, "stop_v": stop, "points": points, "change": "manual_review_required"}
    span = stop - start
    padding = abs(span) * 0.25 if span else (_optional_float(current.get("step_v")) or 0.01)
    return {"start_v": start - padding, "stop_v": stop + padding, "points": max(points + 2, points), "change": "broaden"}


def _proposal_density_summary(values: list[float]) -> dict[str, Any]:
    return {
        "finite_count": len(values),
        "min": min(values) if values else None,
        "max": max(values) if values else None,
        "has_positive": any(value > 0 for value in values),
        "has_negative": any(value < 0 for value in values),
    }


def _proposal_preserved_settings(analysis_dir: Path) -> dict[str, Any]:
    settings: dict[str, Any] = {
        "source": "not available",
        "recipes": {},
    }
    manifest_path = analysis_dir / "hall_suite_analysis_manifest.json"
    if not manifest_path.exists():
        return settings
    manifest = _load_package_manifest(manifest_path)
    intake_value = manifest.get("result_intake_json")
    if not intake_value:
        return settings
    intake_path = Path(str(intake_value))
    if not intake_path.is_absolute() and not intake_path.exists():
        intake_path = analysis_dir / intake_path
    if not intake_path.exists():
        return settings
    intake = _load_result_intake_json(intake_path)
    package_manifest_value = intake.get("package_manifest_path")
    if not package_manifest_value:
        return settings
    package_manifest_path = Path(str(package_manifest_value))
    if not package_manifest_path.is_absolute() and not package_manifest_path.exists():
        package_manifest_path = intake_path.parent / package_manifest_path
    if not package_manifest_path.exists():
        return settings
    package_manifest = _load_package_manifest(package_manifest_path)
    package_dir = package_manifest_path.parent
    settings["source"] = str(package_manifest_path)
    for key, recipe_path in _package_recipe_paths(package_manifest, package_dir).items():
        recipe = DualGateLockInRecipe.model_validate(load_yaml(recipe_path))
        settings["recipes"][key] = _proposal_recipe_settings(recipe)
    return settings


def _proposal_recipe_settings(recipe: DualGateLockInRecipe) -> dict[str, Any]:
    return {
        "measurement_name": recipe.measurement_name,
        "gate1": _proposal_instrument_settings(recipe.gate1_instrument, recipe.gate1_sweep.current_compliance_a, recipe.gate1_sweep.settle_s),
        "gate2": _proposal_instrument_settings(recipe.gate2_instrument, recipe.gate2_sweep.current_compliance_a, recipe.gate2_sweep.settle_s),
        "lockin": {
            "reference_frequency_hz": recipe.lockin.reference_frequency_hz,
            "sine_output_amplitude_v": recipe.lockin.sine_output_amplitude_v,
            "sensitivity_index": recipe.lockin.sensitivity_index,
            "time_constant_index": recipe.lockin.time_constant_index,
            "settle_time_constants": recipe.lockin.settle_time_constants,
            "read_settle_s": recipe.lockin.read_settle_s,
        },
    }


def _proposal_instrument_settings(instrument: Any, compliance_a: float, settle_s: float) -> dict[str, Any]:
    return {
        "address": instrument.address,
        "terminal": instrument.terminal,
        "voltage_range_v": instrument.voltage_range_v,
        "current_range_a": instrument.current_range_a,
        "nplc": instrument.nplc,
        "source_delay_s": instrument.source_delay_s,
        "current_compliance_a": compliance_a,
        "settle_s": settle_s,
    }


def _proposal_grid_row(axis: str, current: dict[str, Any], proposed: dict[str, Any]) -> str:
    current_axis = current.get(axis) if isinstance(current.get(axis), dict) else {}
    proposed_axis = proposed.get(axis) if isinstance(proposed.get(axis), dict) else {}
    return (
        f"| {axis} | {_fmt_optional(current_axis.get('start_v'))} | {_fmt_optional(current_axis.get('stop_v'))} | "
        f"{_fmt_optional(current_axis.get('points'))} | {_fmt_optional(proposed_axis.get('start_v'))} | "
        f"{_fmt_optional(proposed_axis.get('stop_v'))} | {_fmt_optional(proposed_axis.get('points'))} |"
    )


def _proposal_settings_lines(settings: dict[str, Any]) -> list[str]:
    recipes = settings.get("recipes") if isinstance(settings.get("recipes"), dict) else {}
    if not recipes:
        return ["- Packaged recipe settings were not available; manually preserve Keithley and SR860 settings."]
    lines = [f"- Source manifest: `{settings.get('source')}`"]
    for key, recipe_settings in recipes.items():
        if not isinstance(recipe_settings, dict):
            continue
        lines.append(f"- `{key}` measurement: {recipe_settings.get('measurement_name')}")
        for gate in ["gate1", "gate2"]:
            gate_settings = recipe_settings.get(gate) if isinstance(recipe_settings.get(gate), dict) else {}
            lines.append(
                f"  - {gate}: NPLC={_fmt_optional(gate_settings.get('nplc'))}, "
                f"Vrange={_fmt_optional(gate_settings.get('voltage_range_v'))}, "
                f"Irange={_fmt_optional(gate_settings.get('current_range_a'))}, "
                f"compliance={_fmt_optional(gate_settings.get('current_compliance_a'))}, "
                f"settle={_fmt_optional(gate_settings.get('settle_s'))}"
            )
        lockin = recipe_settings.get("lockin") if isinstance(recipe_settings.get("lockin"), dict) else {}
        lines.append(
            f"  - SR860: f={_fmt_optional(lockin.get('reference_frequency_hz'))} Hz, "
            f"amplitude={_fmt_optional(lockin.get('sine_output_amplitude_v'))} V, "
            f"sensitivity_index={_fmt_optional(lockin.get('sensitivity_index'))}, "
            f"tau_index={_fmt_optional(lockin.get('time_constant_index'))}"
        )
    return lines


def _analysis_csv_path(analysis_dir: Path, manifest_value: Any, fallback_relative: str) -> Path | None:
    if manifest_value is None:
        fallback = analysis_dir / fallback_relative
        return fallback if fallback.exists() else None
    path = Path(str(manifest_value))
    if not path.is_absolute() and not path.exists():
        path = analysis_dir / path
    return path


def _read_analysis_rows(
    path: Path | None,
    expected_columns: list[str],
    label: str,
    issues: list[HallSuiteAnalysisReviewIssue],
    *,
    required: bool,
) -> list[dict[str, str]]:
    if path is None or not path.exists():
        severity = "error" if required else "info"
        message = "missing required CSV" if required else "CSV not present; optional analysis was not run"
        issues.append(HallSuiteAnalysisReviewIssue(severity, f"{label}.exists", f"{message}: {path or 'n/a'}"))
        return []
    try:
        with path.open("r", newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            rows = [dict(row) for row in reader]
            missing = [column for column in expected_columns if column not in (reader.fieldnames or [])]
    except OSError as exc:
        issues.append(HallSuiteAnalysisReviewIssue("error", f"{label}.read", f"could not read CSV: {exc}"))
        return []
    if missing:
        issues.append(HallSuiteAnalysisReviewIssue("error", f"{label}.columns", f"missing columns: {', '.join(missing)}"))
    if required and not rows:
        issues.append(HallSuiteAnalysisReviewIssue("error", f"{label}.rows", "CSV contains no rows"))
    return rows


def _analysis_table_summary(rows: list[dict[str, str]], columns: dict[str, str]) -> dict[str, Any]:
    return {
        "points": len(rows),
        "columns": {
            label: _analysis_range(rows, column)
            for label, column in columns.items()
        },
        "gate_points": len(_analysis_gate_points(rows)),
    }


def _analysis_range(rows: list[dict[str, str]], column: str) -> dict[str, Any]:
    values = [_optional_float(row.get(column)) for row in rows]
    finite = [value for value in values if value is not None]
    signs = {1 if value > 0 else -1 if value < 0 else 0 for value in finite}
    return {
        "finite_count": len(finite),
        "missing_count": len(rows) - len(finite),
        "min": min(finite) if finite else None,
        "max": max(finite) if finite else None,
        "has_positive": 1 in signs,
        "has_negative": -1 in signs,
        "has_zero": 0 in signs,
    }


def _analysis_gate_points(rows: list[dict[str, str]]) -> set[tuple[float, float]]:
    points = set()
    for row in rows:
        gate1 = _optional_float(row.get("gate1_voltage_v"))
        gate2 = _optional_float(row.get("gate2_voltage_v"))
        if gate1 is not None and gate2 is not None:
            points.add((gate1, gate2))
    return points


def _append_hall_suite_analysis_review_issues(
    antisym_rows: list[dict[str, str]],
    zero_rows: list[dict[str, str]],
    mobility_rows: list[dict[str, str]],
    issues: list[HallSuiteAnalysisReviewIssue],
) -> None:
    antisym_points = _analysis_gate_points(antisym_rows)
    zero_points = _analysis_gate_points(zero_rows)
    mobility_points = _analysis_gate_points(mobility_rows)
    if antisym_rows and mobility_rows and antisym_points != mobility_points:
        issues.append(
            HallSuiteAnalysisReviewIssue(
                "error",
                "gate_grid.mobility_vs_antisym",
                f"mobility grid ({len(mobility_points)}) differs from antisym grid ({len(antisym_points)})",
            )
        )
    if zero_rows and mobility_rows and zero_points != mobility_points:
        issues.append(
            HallSuiteAnalysisReviewIssue(
                "error",
                "gate_grid.mobility_vs_zero_corrected",
                f"mobility grid ({len(mobility_points)}) differs from zero-corrected grid ({len(zero_points)})",
            )
        )
    for label, rows, column in [
        ("antisym_density", antisym_rows, "hall_carrier_density_per_m2"),
        ("zero_corrected_density", zero_rows, "hall_carrier_density_per_m2"),
        ("mobility_density", mobility_rows, "hall_carrier_density_per_m2"),
    ]:
        signs = _finite_signs(rows, column)
        if 1 in signs and -1 in signs:
            issues.append(
                HallSuiteAnalysisReviewIssue(
                    "warning",
                    f"{label}.sign_change",
                    "finite carrier density contains both electron-like and hole-like signs",
                )
            )
    _append_offset_warnings(antisym_rows, zero_rows, issues)
    missing_mobility = sum(1 for row in mobility_rows if _optional_float(row.get("mobility_magnitude_cm2_per_v_s")) is None)
    if missing_mobility:
        issues.append(
            HallSuiteAnalysisReviewIssue(
                "warning",
                "mobility.missing",
                f"{missing_mobility} mobility rows are missing finite mobility magnitude",
            )
        )


def _finite_signs(rows: list[dict[str, str]], column: str) -> set[int]:
    signs = set()
    for row in rows:
        value = _optional_float(row.get(column))
        if value is None:
            continue
        if value > 0:
            signs.add(1)
        elif value < 0:
            signs.add(-1)
        else:
            signs.add(0)
    return signs


def _append_offset_warnings(
    antisym_rows: list[dict[str, str]],
    zero_rows: list[dict[str, str]],
    issues: list[HallSuiteAnalysisReviewIssue],
) -> None:
    even_larger = 0
    for row in antisym_rows:
        odd = _optional_float(row.get("hall_antisym_resistance_ohm"))
        even = _optional_float(row.get("field_even_resistance_ohm"))
        if odd is not None and even is not None and abs(even) > abs(odd):
            even_larger += 1
    if even_larger:
        issues.append(
            HallSuiteAnalysisReviewIssue(
                "warning",
                "hall.field_even_offset",
                f"field-even resistance exceeds antisym Hall resistance at {even_larger} gate points",
            )
        )
    zero_large = 0
    sign_changed = 0
    antisym_by_gate = {point: row for point, row in _analysis_rows_by_gate(antisym_rows).items()}
    for point, row in _analysis_rows_by_gate(zero_rows).items():
        field = _optional_float(row.get("field_resistance_ohm"))
        zero = _optional_float(row.get("zero_field_resistance_ohm"))
        if field is not None and zero is not None and abs(field) > 0 and abs(zero) / abs(field) > 0.5:
            zero_large += 1
        antisym_density = _optional_float(antisym_by_gate.get(point, {}).get("hall_carrier_density_per_m2"))
        zero_density = _optional_float(row.get("hall_carrier_density_per_m2"))
        if (
            antisym_density is not None
            and zero_density is not None
            and antisym_density != 0
            and zero_density != 0
            and (antisym_density > 0) != (zero_density > 0)
        ):
            sign_changed += 1
    if zero_large:
        issues.append(
            HallSuiteAnalysisReviewIssue(
                "warning",
                "hall.zero_field_offset",
                f"zero-field Hall resistance is more than 50% of finite-field resistance at {zero_large} gate points",
            )
        )
    if sign_changed:
        issues.append(
            HallSuiteAnalysisReviewIssue(
                "warning",
                "hall.zero_correction_sign_change",
                f"zero-field correction changes carrier-density sign at {sign_changed} gate points",
            )
        )


def _analysis_rows_by_gate(rows: list[dict[str, str]]) -> dict[tuple[float, float], dict[str, str]]:
    by_gate = {}
    for row in rows:
        gate1 = _optional_float(row.get("gate1_voltage_v"))
        gate2 = _optional_float(row.get("gate2_voltage_v"))
        if gate1 is not None and gate2 is not None:
            by_gate[(gate1, gate2)] = row
    return by_gate


def _analysis_summary_table_row(label: str, summary: Any) -> str:
    if not isinstance(summary, dict):
        return f"| {label} | 0 | n/a |"
    columns = summary.get("columns") if isinstance(summary.get("columns"), dict) else {}
    return f"| {label} | {summary.get('gate_points', 0)} | {', '.join(columns) or 'n/a'} |"


def _analysis_range_lines(summary: Any) -> list[str]:
    if not isinstance(summary, dict):
        return ["- n/a"]
    columns = summary.get("columns") if isinstance(summary.get("columns"), dict) else {}
    if not columns:
        return ["- n/a"]
    lines = []
    for label, stats in columns.items():
        if not isinstance(stats, dict) or stats.get("finite_count", 0) == 0:
            lines.append(f"- `{label}`: no finite values")
            continue
        lines.append(
            f"- `{label}`: min={_fmt_optional(stats.get('min'))}, "
            f"max={_fmt_optional(stats.get('max'))}, finite={stats.get('finite_count')}, missing={stats.get('missing_count')}"
        )
    return lines


def _load_package_manifest(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _annotate_approved_next_scan_package(
    result: HallSuiteAcquisitionPackageResult,
    proposal_path: Path,
    approval_review_path: Path,
    proposal: dict[str, Any],
) -> None:
    manifest = _load_package_manifest(result.manifest_path)
    manifest["approved_next_scan"] = {
        "proposal_json": str(proposal_path),
        "approval_review": str(approval_review_path),
        "strategy": proposal.get("strategy"),
        "proposed_gate_grid": proposal.get("proposed_gate_grid"),
        "hardware_recipe_written_by_proposal": proposal.get("hardware_recipe_written"),
        "requires_lab_approval": proposal.get("requires_lab_approval"),
        "preserve_measurement_settings": proposal.get("preserve_measurement_settings"),
    }
    result.manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    with result.runbook_path.open("a", encoding="utf-8") as handle:
        handle.write("\n")
        handle.write(format_dual_gate_lockin_hall_suite_approved_next_scan_package_addendum(proposal_path, approval_review_path, proposal))


def format_dual_gate_lockin_hall_suite_approved_next_scan_package_addendum(
    proposal_path: Path,
    approval_review_path: Path,
    proposal: dict[str, Any],
) -> str:
    current = proposal.get("current_gate_grid") if isinstance(proposal.get("current_gate_grid"), dict) else {}
    proposed = proposal.get("proposed_gate_grid") if isinstance(proposal.get("proposed_gate_grid"), dict) else {}
    settings = proposal.get("preserve_measurement_settings") if isinstance(proposal.get("preserve_measurement_settings"), dict) else {}
    return "\n".join(
        [
            "## Approved Next-Scan Provenance",
            "",
            f"- Proposal JSON copied from: `{proposal_path}`",
            f"- Approval review copied from: `{approval_review_path}`",
            f"- Strategy: `{proposal.get('strategy')}`",
            "",
            "### Gate Grid Change",
            "",
            "| Axis | Previous start (V) | Previous stop (V) | Previous points | Package start (V) | Package stop (V) | Package points |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
            _proposal_grid_row("gate1", current, proposed),
            _proposal_grid_row("gate2", current, proposed),
            "",
            "### Measurement Settings To Preserve",
            "",
            *_proposal_settings_lines(settings),
            "",
            "### Hardware Policy",
            "",
            "- Use the chunked acquisition commands in this runbook.",
            "- After the lab run, use `ptm dual-gate-lockin-hall-suite-intake` against this package before Hall analysis.",
            "- Do not change Keithley NPLC/range/compliance or SR860 settings on the lab laptop unless the change is recorded in the lab notebook and a new package is produced.",
            "",
        ]
    )


def _package_recipe_paths(manifest: dict[str, Any], package_dir: Path) -> dict[str, Path]:
    copied = manifest.get("copied_recipes")
    if not isinstance(copied, dict):
        raise ValueError("Package manifest is missing copied_recipes")
    mapping = {
        "longitudinal": copied.get("longitudinal"),
        "plus": copied.get("plus"),
        "minus": copied.get("minus"),
        "zero": copied.get("zero"),
    }
    paths = {}
    for key, value in mapping.items():
        if not value:
            continue
        path = Path(value)
        if not path.is_absolute():
            path = package_dir / path
        if not path.exists():
            raise FileNotFoundError(f"Packaged {key} recipe does not exist: {path}")
        paths[key] = path
    for key in ["longitudinal", "plus", "minus"]:
        if key not in paths:
            raise ValueError(f"Package manifest is missing copied recipe for {key}")
    return paths


def _compare_run_to_packaged_recipe(
    key: str,
    run_dir: Path,
    recipe_path: Path,
) -> list[HallSuiteResultIntakeIssue]:
    issues: list[HallSuiteResultIntakeIssue] = []
    metadata = read_dual_gate_lockin_metadata(run_dir)
    expected_recipe = DualGateLockInRecipe.model_validate(load_yaml(recipe_path))
    actual_recipe_data = metadata.get("recipe")
    if not isinstance(actual_recipe_data, dict):
        return [HallSuiteResultIntakeIssue("error", f"{key}.recipe_snapshot", "run metadata does not contain a recipe snapshot")]
    try:
        actual_recipe = DualGateLockInRecipe.model_validate(actual_recipe_data)
    except Exception as exc:
        return [HallSuiteResultIntakeIssue("error", f"{key}.recipe_snapshot", f"invalid run recipe snapshot: {type(exc).__name__}: {exc}")]

    if actual_recipe.model_dump(mode="json") != expected_recipe.model_dump(mode="json"):
        issues.append(HallSuiteResultIntakeIssue("error", f"{key}.recipe_match", "run recipe snapshot differs from packaged recipe"))
    if metadata.get("measurement_name") != expected_recipe.measurement_name:
        issues.append(
            HallSuiteResultIntakeIssue(
                "error",
                f"{key}.measurement_name",
                f"expected {expected_recipe.measurement_name}, got {metadata.get('measurement_name') or 'missing'}",
            )
        )
    expected_signature = dual_gate_lockin_grid_signature(expected_recipe)
    actual_signature = metadata.get("planned_gate_grid_signature")
    if actual_signature != expected_signature:
        issues.append(
            HallSuiteResultIntakeIssue(
                "error",
                f"{key}.grid_signature",
                f"expected {expected_signature}, got {actual_signature or 'missing'}",
            )
        )
    return issues


def _check_condition_drift_for_run(
    key: str,
    packaged_recipe: DualGateLockInRecipe,
    metadata: dict[str, Any],
    issues: list[HallSuiteConditionDriftIssue],
) -> None:
    run_recipe = metadata.get("recipe")
    if not isinstance(run_recipe, dict):
        issues.append(
            HallSuiteConditionDriftIssue(
                "error",
                key,
                "recipe",
                "recipe snapshot",
                None,
                "run metadata is missing recipe snapshot",
            )
        )
        return
    expected = packaged_recipe.model_dump(mode="json")
    for instrument_key in ["gate1_instrument", "gate2_instrument"]:
        for field in ["address", "terminal", "voltage_range_v", "current_range_a", "nplc", "source_delay_s"]:
            _append_condition_issue_if_different(
                issues,
                key,
                f"{instrument_key}.{field}",
                _nested_get(expected, instrument_key, field),
                _nested_get(run_recipe, instrument_key, field),
            )
    for sweep_key in ["gate1_sweep", "gate2_sweep"]:
        for field in ["current_compliance_a", "settle_s"]:
            _append_condition_issue_if_different(
                issues,
                key,
                f"{sweep_key}.{field}",
                _nested_get(expected, sweep_key, field),
                _nested_get(run_recipe, sweep_key, field),
            )
    expected_lockin = expected.get("lockin") if isinstance(expected.get("lockin"), dict) else {}
    run_lockin = run_recipe.get("lockin") if isinstance(run_recipe.get("lockin"), dict) else {}
    for field in sorted(set(expected_lockin_settings(expected_lockin)) | {"read_settle_s", "settle_time_constants"}):
        _append_condition_issue_if_different(
            issues,
            key,
            f"lockin.{field}",
            expected_lockin.get(field),
            run_lockin.get(field),
        )
    expected_topology = expected.get("topology") if isinstance(expected.get("topology"), dict) else {}
    run_topology = run_recipe.get("topology") if isinstance(run_recipe.get("topology"), dict) else {}
    for field in [
        "voltage_probe_role",
        "lockin_input_contacts",
        "excitation_contacts",
        "source_contact",
        "drain_contact",
        "magnetic_field_t",
        "channel_length_m",
        "channel_width_m",
        "bias_resistor_ohm",
        "topology_layout",
    ]:
        _append_condition_issue_if_different(
            issues,
            key,
            f"topology.{field}",
            expected_topology.get(field),
            run_topology.get(field),
        )
    for role, instrument_key, sweep_key in [
        ("gate1", "gate1_instrument", "gate1_sweep"),
        ("gate2", "gate2_instrument", "gate2_sweep"),
    ]:
        configured = metadata.get(f"configured_{role}_smu")
        if not isinstance(configured, dict):
            issues.append(
                HallSuiteConditionDriftIssue(
                    "error",
                    key,
                    f"configured_{role}_smu",
                    "metadata snapshot",
                    None,
                    "run metadata is missing configured SMU snapshot",
                )
            )
            continue
        expected_config = {
            "current_compliance_a": _nested_get(expected, sweep_key, "current_compliance_a"),
            "voltage_range_v": _nested_get(expected, instrument_key, "voltage_range_v"),
            "current_range_a": _nested_get(expected, instrument_key, "current_range_a"),
            "terminal": _nested_get(expected, instrument_key, "terminal"),
            "nplc": _nested_get(expected, instrument_key, "nplc"),
            "source_delay_s": _nested_get(expected, instrument_key, "source_delay_s"),
        }
        for field, expected_value in expected_config.items():
            _append_condition_issue_if_different(
                issues,
                key,
                f"configured_{role}_smu.{field}",
                expected_value,
                configured.get(field),
            )
        readback_check = metadata.get(f"configured_{role}_smu_readback_check")
        if isinstance(readback_check, dict) and readback_check.get("matched") is False:
            issues.append(
                HallSuiteConditionDriftIssue(
                    "error",
                    key,
                    f"configured_{role}_smu_readback_check",
                    True,
                    False,
                    "Keithley readback did not match configured recipe values during run",
                )
            )
    if metadata.get("lockin_settings_readback_available") is True and metadata.get("lockin_settings_readback_matched") is False:
        issues.append(
            HallSuiteConditionDriftIssue(
                "error",
                key,
                "lockin_settings_readback",
                True,
                False,
                "SR860 readback did not match configured recipe values during run",
            )
        )


def _build_condition_drift_payload(manifest_path: Path, intake_path: Path) -> dict[str, Any]:
    package_dir = manifest_path.parent
    manifest = _load_package_manifest(manifest_path)
    intake = _load_result_intake_json(intake_path)
    recipe_paths = _package_recipe_paths(manifest, package_dir)
    runs = intake.get("runs")
    if not isinstance(runs, dict):
        raise ValueError("result_intake.json is missing runs")
    issues: list[HallSuiteConditionDriftIssue] = []
    run_payloads: dict[str, dict[str, Any]] = {}
    for key, recipe_path in recipe_paths.items():
        run_info = runs.get(key)
        if not isinstance(run_info, dict) or not run_info.get("run_dir"):
            if key in {"longitudinal", "plus", "minus"}:
                issues.append(
                    HallSuiteConditionDriftIssue(
                        "error",
                        key,
                        "run_dir",
                        str(recipe_path),
                        None,
                        "required run is missing from result_intake.json",
                    )
                )
            continue
        run_dir = Path(str(run_info["run_dir"]))
        metadata = read_dual_gate_lockin_metadata(run_dir)
        run_payloads[key] = {
            "run_dir": str(run_dir),
            "metadata_path": str(run_dir / "metadata.json"),
        }
        packaged_recipe = DualGateLockInRecipe.model_validate(load_yaml(recipe_path))
        _check_condition_drift_for_run(key, packaged_recipe, metadata, issues)
    return {
        "package_manifest_path": str(manifest_path),
        "result_intake_json_path": str(intake_path),
        "accepted": not any(issue.severity == "error" for issue in issues),
        "runs": run_payloads,
        "issues": [issue.__dict__ for issue in issues],
    }


def _build_condition_snapshot_payload(manifest_path: Path, intake_path: Path) -> dict[str, Any]:
    intake = _load_result_intake_json(intake_path)
    runs = intake.get("runs")
    if not isinstance(runs, dict):
        raise ValueError("result_intake.json is missing runs")
    rows: list[dict[str, Any]] = []
    for key in ["longitudinal", "plus", "minus", "zero"]:
        run_info = runs.get(key)
        if not isinstance(run_info, dict) or not run_info.get("run_dir"):
            continue
        run_dir = Path(str(run_info["run_dir"]))
        metadata = read_dual_gate_lockin_metadata(run_dir)
        rows.append(_condition_snapshot_row(key, run_dir, metadata))
    return {
        "package_manifest_path": str(manifest_path),
        "result_intake_json_path": str(intake_path),
        "runs": rows,
    }


def _condition_snapshot_row(run_key: str, run_dir: Path, metadata: dict[str, Any]) -> dict[str, Any]:
    recipe = metadata.get("recipe") if isinstance(metadata.get("recipe"), dict) else {}
    lockin_recipe = recipe.get("lockin") if isinstance(recipe.get("lockin"), dict) else {}
    return {
        "run_key": run_key,
        "run_dir": str(run_dir),
        "measurement_name": metadata.get("measurement_name"),
        "completed": metadata.get("completed"),
        "points_written": metadata.get("points_written"),
        "planned_points": metadata.get("planned_points"),
        "voltage_probe_role": metadata.get("voltage_probe_role"),
        "magnetic_field_t": metadata.get("magnetic_field_t"),
        "topology": _condition_snapshot_topology(recipe),
        "gate1": _condition_snapshot_gate(metadata, recipe, "gate1"),
        "gate2": _condition_snapshot_gate(metadata, recipe, "gate2"),
        "lockin": {
            "address": lockin_recipe.get("address"),
            "sensitivity_index": lockin_recipe.get("sensitivity_index"),
            "time_constant_index": lockin_recipe.get("time_constant_index"),
            "read_settle_s": lockin_recipe.get("read_settle_s"),
            "settle_time_constants": lockin_recipe.get("settle_time_constants"),
            "time_constant_s": metadata.get("lockin_time_constant_s"),
            "readback_available": metadata.get("lockin_settings_readback_available"),
            "readback_matched": metadata.get("lockin_settings_readback_matched"),
        },
    }


def _condition_snapshot_topology(recipe: dict[str, Any]) -> dict[str, Any]:
    topology = recipe.get("topology") if isinstance(recipe.get("topology"), dict) else {}
    return {
        "voltage_probe_role": topology.get("voltage_probe_role"),
        "lockin_input_contacts": topology.get("lockin_input_contacts"),
        "excitation_contacts": topology.get("excitation_contacts"),
        "source_contact": topology.get("source_contact"),
        "drain_contact": topology.get("drain_contact"),
        "magnetic_field_t": topology.get("magnetic_field_t"),
        "channel_length_m": topology.get("channel_length_m"),
        "channel_width_m": topology.get("channel_width_m"),
        "bias_resistor_ohm": topology.get("bias_resistor_ohm"),
        "topology_layout": topology.get("topology_layout"),
    }


def _hall_suite_topology_contract(recipes: dict[str, DualGateLockInRecipe]) -> dict[str, dict[str, Any]]:
    return {
        key: _condition_snapshot_topology(recipe.model_dump(mode="json"))
        for key, recipe in recipes.items()
    }


def _format_hall_suite_topology_contract_rows(topology_contract: dict[str, dict[str, Any]]) -> list[str]:
    rows = []
    for key in ["longitudinal", "plus", "minus", "zero"]:
        if key not in topology_contract:
            continue
        topology = topology_contract.get(key) or {}
        rows.append(
            "| "
            f"{key} | "
            f"{_fmt_optional(topology.get('voltage_probe_role'))} | "
            f"{_fmt_optional(topology.get('magnetic_field_t'))} | "
            f"{_fmt_contact_list(topology.get('excitation_contacts'))} | "
            f"{_fmt_contact_list(topology.get('lockin_input_contacts'))} | "
            f"{_fmt_optional(topology.get('channel_length_m'))} | "
            f"{_fmt_optional(topology.get('channel_width_m'))} | "
            f"{_fmt_optional(topology.get('topology_layout'))} |"
        )
    return rows or ["| n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |"]


def _condition_snapshot_gate(metadata: dict[str, Any], recipe: dict[str, Any], gate: str) -> dict[str, Any]:
    instrument = recipe.get(f"{gate}_instrument") if isinstance(recipe.get(f"{gate}_instrument"), dict) else {}
    sweep = recipe.get(f"{gate}_sweep") if isinstance(recipe.get(f"{gate}_sweep"), dict) else {}
    configured = metadata.get(f"configured_{gate}_smu") if isinstance(metadata.get(f"configured_{gate}_smu"), dict) else {}
    readback_check = (
        metadata.get(f"configured_{gate}_smu_readback_check")
        if isinstance(metadata.get(f"configured_{gate}_smu_readback_check"), dict)
        else {}
    )
    return {
        "address": instrument.get("address"),
        "terminal": configured.get("terminal", instrument.get("terminal")),
        "voltage_range_v": configured.get("voltage_range_v", instrument.get("voltage_range_v")),
        "current_range_a": configured.get("current_range_a", instrument.get("current_range_a")),
        "nplc": configured.get("nplc", instrument.get("nplc")),
        "current_compliance_a": configured.get("current_compliance_a", sweep.get("current_compliance_a")),
        "source_delay_s": configured.get("source_delay_s", instrument.get("source_delay_s")),
        "readback_matched": readback_check.get("matched"),
    }


def _package_manifest_path_from_intake(intake_json_path: Path, intake: dict[str, Any]) -> Path:
    value = intake.get("package_manifest_path")
    if not value:
        raise ValueError("result_intake.json is missing package_manifest_path")
    path = Path(str(value))
    if not path.is_absolute():
        candidate = intake_json_path.parent / path
        path = candidate if candidate.exists() else path
    if not path.exists():
        raise FileNotFoundError(f"Package manifest from result_intake.json does not exist: {path}")
    return path


def _append_condition_issue_if_different(
    issues: list[HallSuiteConditionDriftIssue],
    run_key: str,
    field: str,
    expected: Any,
    actual: Any,
) -> None:
    if _condition_values_equal(expected, actual):
        return
    issues.append(
        HallSuiteConditionDriftIssue(
            "error",
            run_key,
            field,
            expected,
            actual,
            "acquisition condition differs from packaged recipe",
        )
    )


def _condition_values_equal(expected: Any, actual: Any) -> bool:
    if expected is None and actual is None:
        return True
    if isinstance(expected, (int, float)) or isinstance(actual, (int, float)):
        expected_float = _optional_float(expected)
        actual_float = _optional_float(actual)
        if expected_float is None or actual_float is None:
            return False
        return abs(expected_float - actual_float) <= max(1e-12, abs(expected_float) * 1e-9)
    return expected == actual


def _nested_get(data: dict[str, Any], *keys: str) -> Any:
    cursor: Any = data
    for key in keys:
        if not isinstance(cursor, dict):
            return None
        cursor = cursor.get(key)
    return cursor


def _run_role_fields(run_dirs: dict[str, Path]) -> dict[str, dict[str, Any]]:
    fields: dict[str, dict[str, Any]] = {}
    for key, run_dir in run_dirs.items():
        metadata = read_dual_gate_lockin_metadata(run_dir)
        recipe = metadata.get("recipe") if isinstance(metadata.get("recipe"), dict) else {}
        topology = recipe.get("topology") if isinstance(recipe.get("topology"), dict) else {}
        fields[key] = {
            "voltage_probe_role": topology.get("voltage_probe_role"),
            "magnetic_field_t": topology.get("magnetic_field_t"),
            "measurement_name": metadata.get("measurement_name"),
        }
    return fields


def _run_topology_summary(run_dir: Path) -> dict[str, Any]:
    metadata = read_dual_gate_lockin_metadata(run_dir)
    recipe = metadata.get("recipe") if isinstance(metadata.get("recipe"), dict) else {}
    return _condition_snapshot_topology(recipe)


def _check_intake_roles(
    role_fields: dict[str, dict[str, Any]],
    issues: list[HallSuiteResultIntakeIssue],
) -> None:
    expected_roles = {"longitudinal": "longitudinal", "plus": "hall", "minus": "hall", "zero": "hall"}
    for key, expected in expected_roles.items():
        if key not in role_fields:
            continue
        actual = role_fields[key].get("voltage_probe_role")
        if actual != expected:
            issues.append(HallSuiteResultIntakeIssue("error", f"{key}.voltage_probe_role", f"expected {expected}, got {actual or 'missing'}"))
    if "zero" in role_fields:
        zero_b = role_fields["zero"].get("magnetic_field_t")
        if not isinstance(zero_b, (int, float)) or abs(zero_b) > 1e-12:
            issues.append(HallSuiteResultIntakeIssue("error", "zero.magnetic_field_t", "zero-field run must have B = 0"))


def _suite_key_label(key: str) -> str:
    return {
        "longitudinal": "Longitudinal Vxx",
        "plus": "+B Hall Vxy",
        "minus": "-B Hall Vxy",
        "zero": "0B Hall Vxy",
    }.get(key, key)


def _copy_labeled_files(
    files: list[str | Path],
    target_dir: Path,
    kind: str,
) -> list[dict[str, str]]:
    copied: list[dict[str, str]] = []
    for value in files:
        source = Path(value)
        if not source.exists() or not source.is_file():
            raise FileNotFoundError(f"{kind} file does not exist: {source}")
        target_dir.mkdir(parents=True, exist_ok=True)
        target = _unique_target_path(target_dir, source.name)
        shutil.copy2(source, target)
        copied.append(
            {
                "kind": kind,
                "source": str(source),
                "path": target.relative_to(target_dir.parent).as_posix(),
            }
        )
    return copied


def _copy_four_terminal_ac_smoke_intake(source_path: str | Path, package_dir: Path) -> dict[str, Any]:
    source = Path(source_path)
    if not source.exists() or not source.is_file():
        raise FileNotFoundError(f"four-terminal AC smoke intake JSON does not exist: {source}")
    with source.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"four-terminal AC smoke intake JSON must contain an object: {source}")
    summary = _validate_four_terminal_ac_smoke_intake_payload(payload, source)
    target_dir = package_dir / "prerequisites"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = _unique_target_path(target_dir, source.name)
    shutil.copy2(source, target)
    return {
        **summary,
        "source": str(source),
        "path": target.relative_to(package_dir).as_posix(),
    }


def _validate_four_terminal_ac_smoke_intake_payload(payload: dict[str, Any], source: Path) -> dict[str, Any]:
    issues: list[str] = []

    def require(condition: bool, message: str) -> None:
        if not condition:
            issues.append(message)

    excitation_contacts = tuple(str(contact) for contact in (payload.get("topology_excitation_contacts") or ()))
    lockin_contacts = tuple(str(contact) for contact in (payload.get("topology_lockin_input_contacts") or ()))
    require(payload.get("accepted") is True, "accepted must be true")
    require(payload.get("hardware_guard_required") is True, "hardware_guard_required must be true")
    require(payload.get("hardware_guard_present") is True, "hardware_guard_present must be true")
    require(payload.get("hardware_guard_accepted") is True, "hardware_guard_accepted must be true")
    require(bool(str(payload.get("hardware_guard_approval_note") or "").strip()), "hardware_guard_approval_note is required")
    require(payload.get("lockin_voltage_input") == "a-b", "lockin_voltage_input must be a-b")
    require(payload.get("source_nplc") is not None, "source_nplc is required")
    require(payload.get("source_voltage_range_v") is not None, "source_voltage_range_v is required")
    require(payload.get("source_current_range_a") is not None, "source_current_range_a is required")
    require(payload.get("source_current_compliance_a") is not None, "source_current_compliance_a is required")
    require(len(excitation_contacts) == 2, "topology_excitation_contacts must contain two contacts")
    require(len(lockin_contacts) == 2, "topology_lockin_input_contacts must contain two contacts")
    require(not (set(excitation_contacts) & set(lockin_contacts)), "excitation and SR860 voltage contacts must not overlap")
    guard_point_count = payload.get("hardware_guard_point_count")
    guard_max_points = payload.get("hardware_guard_max_points")
    require(isinstance(guard_point_count, int) and guard_point_count > 0, "hardware_guard_point_count must be a positive integer")
    require(isinstance(guard_max_points, int) and guard_max_points > 0, "hardware_guard_max_points must be a positive integer")
    if isinstance(guard_point_count, int) and isinstance(guard_max_points, int):
        require(guard_point_count <= guard_max_points, "hardware_guard_point_count exceeds hardware_guard_max_points")
    if issues:
        joined = "; ".join(issues)
        raise ValueError(f"four-terminal AC smoke intake prerequisite failed for {source}: {joined}")
    return {
        "accepted": True,
        "measurement_name": payload.get("measurement_name"),
        "measurement_geometry": payload.get("measurement_geometry"),
        "hardware_guard_approval_note": str(payload.get("hardware_guard_approval_note") or "").strip(),
        "hardware_guard_point_count": guard_point_count,
        "hardware_guard_max_points": guard_max_points,
        "lockin_voltage_input": payload.get("lockin_voltage_input"),
        "topology_excitation_contacts": list(excitation_contacts),
        "topology_lockin_input_contacts": list(lockin_contacts),
        "source_nplc": payload.get("source_nplc"),
        "source_voltage_range_v": payload.get("source_voltage_range_v"),
        "source_current_range_a": payload.get("source_current_range_a"),
        "source_current_compliance_a": payload.get("source_current_compliance_a"),
    }


def _unique_target_path(directory: Path, filename: str) -> Path:
    candidate = directory / _safe_name(filename)
    if not candidate.exists():
        return candidate
    stem = candidate.stem
    suffix = candidate.suffix
    for index in range(2, 1000):
        next_candidate = directory / f"{stem}_{index:02d}{suffix}"
        if not next_candidate.exists():
            return next_candidate
    raise FileExistsError(f"Could not create a unique target filename for {filename}")


def _safe_name(value: str) -> str:
    cleaned = "".join(char if char.isalnum() or char in {"-", "_", "."} else "_" for char in value.strip())
    return cleaned.strip("_") or "hall_suite_package"


def _recipe_variant(
    base_data: dict[str, Any],
    *,
    measurement_name: str,
    voltage_probe_role: str,
    magnetic_field_t: float | None,
    lockin_input_contacts: list[str] | None,
    channel_length_m: float | None,
    channel_width_m: float | None,
    run_output_directory: str | Path | None,
) -> dict[str, Any]:
    data = dict(base_data)
    data["measurement_name"] = measurement_name
    topology = dict(data.get("topology") or {})
    topology["voltage_probe_role"] = voltage_probe_role
    if magnetic_field_t is None:
        topology.pop("magnetic_field_t", None)
    else:
        topology["magnetic_field_t"] = magnetic_field_t
    if lockin_input_contacts is not None:
        topology["lockin_input_contacts"] = list(lockin_input_contacts)
    if voltage_probe_role == "longitudinal":
        if channel_length_m is not None:
            topology["channel_length_m"] = channel_length_m
        if channel_width_m is not None:
            topology["channel_width_m"] = channel_width_m
    else:
        topology.pop("channel_length_m", None)
        topology.pop("channel_width_m", None)
    data["topology"] = topology
    if run_output_directory is not None:
        data["output"] = {**dict(data.get("output") or {}), "directory": str(run_output_directory)}
    DualGateLockInRecipe.model_validate(data)
    return data


def _write_recipe(path: Path, data: dict[str, Any], *, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise FileExistsError(f"Recipe already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, sort_keys=False)


def _check_role(label: str, recipe: DualGateLockInRecipe, expected: str, issues: list[HallSuiteIssue]) -> None:
    if recipe.topology.voltage_probe_role != expected:
        issues.append(
            HallSuiteIssue(
                "error",
                f"{label}.voltage_probe_role",
                f"expected {expected}, got {recipe.topology.voltage_probe_role}",
            )
        )


def _check_magnetic_fields(
    plus: DualGateLockInRecipe,
    minus: DualGateLockInRecipe,
    zero: DualGateLockInRecipe | None,
    issues: list[HallSuiteIssue],
) -> None:
    plus_b = plus.topology.magnetic_field_t
    minus_b = minus.topology.magnetic_field_t
    if plus_b is None or plus_b <= 0:
        issues.append(HallSuiteIssue("error", "plus.magnetic_field_t", "positive-field Hall recipe must have B > 0"))
    if minus_b is None or minus_b >= 0:
        issues.append(HallSuiteIssue("error", "minus.magnetic_field_t", "negative-field Hall recipe must have B < 0"))
    if plus_b is not None and minus_b is not None and abs(plus_b + minus_b) > max(1e-12, abs(plus_b) * 1e-9):
        issues.append(HallSuiteIssue("error", "magnetic_field_t", "+B and -B recipes must use equal magnitude fields"))
    if zero is not None:
        zero_b = zero.topology.magnetic_field_t
        if zero_b is None or abs(zero_b) > 1e-12:
            issues.append(HallSuiteIssue("error", "zero.magnetic_field_t", "zero-field Hall recipe must have B = 0"))


def _check_longitudinal_geometry(recipe: DualGateLockInRecipe, issues: list[HallSuiteIssue]) -> None:
    if recipe.topology.channel_length_m is None or recipe.topology.channel_width_m is None:
        issues.append(
            HallSuiteIssue(
                "error",
                "longitudinal.channel_geometry",
                "longitudinal recipe must declare channel_length_m and channel_width_m",
            )
        )


def _check_hall_geometry(label: str, recipe: DualGateLockInRecipe, issues: list[HallSuiteIssue]) -> None:
    if recipe.topology.channel_length_m is not None or recipe.topology.channel_width_m is not None:
        issues.append(HallSuiteIssue("error", f"{label}.channel_geometry", "Hall recipes must not declare channel L/W"))


def _compare_topology_shared_fields(
    label: str,
    reference: DualGateLockInRecipe,
    candidate: DualGateLockInRecipe,
    issues: list[HallSuiteIssue],
) -> None:
    ignored = {
        "voltage_probe_role",
        "lockin_input_contacts",
        "magnetic_field_t",
        "channel_length_m",
        "channel_width_m",
        "notes",
    }
    reference_topology = reference.topology.model_dump(mode="json")
    candidate_topology = candidate.topology.model_dump(mode="json")
    mismatches = [
        key
        for key, value in reference_topology.items()
        if key not in ignored and candidate_topology.get(key) != value
    ]
    if mismatches:
        issues.append(
            HallSuiteIssue(
                "error",
                "topology",
                f"{label} recipe differs from longitudinal recipe in {', '.join(mismatches)}",
            )
        )


def _fmt_field(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.6g} T"


def _fmt_optional(value: object) -> str:
    return "auto" if value is None else str(value)


def _fmt_contact_list(value: object) -> str:
    if isinstance(value, (list, tuple)):
        contacts = [str(contact).strip() for contact in value if str(contact).strip()]
        return ", ".join(contacts) if contacts else "n/a"
    return "n/a" if value is None else str(value)


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        parsed = float(value)
    else:
        text = str(value).strip()
        if not text:
            return None
        try:
            parsed = float(text)
        except ValueError:
            return None
    return parsed if isfinite(parsed) else None
