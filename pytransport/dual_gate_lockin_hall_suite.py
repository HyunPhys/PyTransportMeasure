"""Template helpers for a Hall-bar dual-gate lock-in measurement suite."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import datetime
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
    extras = []
    extras.extend(_copy_labeled_files(chunk_feedback_files or [], package_dir / "chunk_feedback", "chunk_feedback"))
    extras.extend(_copy_labeled_files(preflight_files or [], package_dir / "preflight", "preflight"))
    extras.extend(_copy_labeled_files(note_files or [], package_dir / "notes", "note"))

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
        ),
        encoding="utf-8",
    )
    manifest_path = package_dir / "package_manifest.json"
    manifest = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "package_name": base_name,
        "source_recipes": {
            "longitudinal": str(audit.longitudinal_recipe),
            "plus_hall": str(audit.plus_hall_recipe),
            "minus_hall": str(audit.minus_hall_recipe),
            "zero_hall": str(audit.zero_hall_recipe) if audit.zero_hall_recipe is not None else None,
        },
        "copied_recipes": {key: path.relative_to(package_dir).as_posix() for key, path in copied_recipes.items()},
        "compatible": audit.compatible,
        "point_count": audit.point_count,
        "chunk_size": chunk_size,
        "max_hardware_points": max_hardware_points,
        "accepted_previous_run": str(accepted_previous_run) if accepted_previous_run is not None else None,
        "acquisition_note": acquisition_note,
        "extras": extras,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    zip_path = Path(shutil.make_archive(str(package_dir), "zip", root_dir=package_dir))
    return HallSuiteAcquisitionPackageResult(package_dir, recipes_dir, runbook_path, manifest_path, zip_path)


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

    errors = [issue for issue in issues if issue.severity == "error"]
    accepted = not errors
    report_text = format_dual_gate_lockin_hall_suite_result_intake(
        manifest_path,
        manifest,
        suite_audit,
        run_audits,
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
            }
            for key, audit in run_audits.items()
        },
    }
    json_path.write_text(json.dumps(json_payload, indent=2, sort_keys=True), encoding="utf-8")
    return HallSuiteResultIntake(manifest_path, accepted, report_path, json_path, tuple(issues))


def format_dual_gate_lockin_hall_suite_result_intake(
    manifest_path: Path,
    manifest: dict[str, Any],
    suite_audit: HallSuiteAudit,
    run_audits: dict[str, Any],
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
    lines.extend(["## Intake Issues", ""])
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


def _resolve_package_manifest_path(package_manifest_or_dir: str | Path) -> Path:
    path = Path(package_manifest_or_dir)
    if path.is_dir():
        path = path / "package_manifest.json"
    if not path.exists():
        raise FileNotFoundError(f"Package manifest does not exist: {path}")
    return path


def _load_package_manifest(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


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
