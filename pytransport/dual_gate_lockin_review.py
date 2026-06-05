"""Review helpers for saved dual-gate lock-in runs."""

from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Any

from .dual_gate_lockin import planned_dual_gate_lockin_grid
from .measurement_context import format_contact_list, format_geometry, format_lockin_contact_context
from .dual_gate_review import fmt
from .preflight import compare_lockin_settings, lockin_settings_ok
from .recipes import DualGateLockInRecipe
from .single_gate_review import current_color, legend_svg, mean, parse_bool, parse_optional_float


@dataclass(frozen=True)
class DualGateLockInAcceptanceIssue:
    severity: str
    check: str
    message: str


@dataclass(frozen=True)
class DualGateLockInAcceptance:
    run_dir: Path
    accepted: bool
    measurement_type: str | None
    completed: bool | None
    points_written: int | None
    planned_points: int | None
    remaining_points: int | None
    gate1_leakage_abs_max_a: float | None
    gate2_leakage_abs_max_a: float | None
    gate1_compliance_a: float | None
    gate2_compliance_a: float | None
    gate1_leakage_compliance_margin: float | None
    gate2_leakage_compliance_margin: float | None
    issues: tuple[DualGateLockInAcceptanceIssue, ...]


SCALE_UP_BLOCKING_ACCEPTANCE_WARNING_CHECKS = frozenset(
    {
        "gate1_leakage",
        "gate2_leakage",
        "gate1_leakage_margin",
        "gate2_leakage_margin",
    }
)


@dataclass(frozen=True)
class DualGateLockInScaleUpIssue:
    severity: str
    check: str
    message: str


@dataclass(frozen=True)
class DualGateLockInScaleUpAudit:
    previous_run_dir: Path
    compatible: bool
    previous_points: int | None
    candidate_points: int
    previous_grid_signature: str | None
    issues: tuple[DualGateLockInScaleUpIssue, ...]


@dataclass(frozen=True)
class DualGateLockInSummary:
    run_dir: Path
    measurement_name: str
    measurement_geometry: str
    topology_layout: str | None
    lockin_voltage_contacts: str
    excitation_contacts: str
    completed: bool | None
    points: int
    gate1_points: int
    gate2_points: int
    gate1_voltage_min_v: float | None
    gate1_voltage_max_v: float | None
    gate2_voltage_min_v: float | None
    gate2_voltage_max_v: float | None
    gate1_leakage_abs_max_a: float | None
    gate2_leakage_abs_max_a: float | None
    lockin_r_min_v: float | None
    lockin_r_max_v: float | None
    lockin_resistance_min_ohm: float | None
    lockin_resistance_max_ohm: float | None
    lockin_conductance_min_s: float | None
    lockin_conductance_max_s: float | None
    lockin_theta_min_deg: float | None
    lockin_theta_max_deg: float | None
    error_type: str | None
    error_message: str | None


def read_dual_gate_lockin_metadata(run_dir: str | Path) -> dict[str, Any]:
    path = Path(run_dir) / "metadata.json"
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def read_dual_gate_lockin_points(run_dir: str | Path) -> list[dict[str, float | int | bool | None]]:
    path = Path(run_dir) / "points.csv"
    if not path.exists():
        raise FileNotFoundError(f"Missing points CSV: {path}")
    rows: list[dict[str, float | int | bool | None]] = []
    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        required = {
            "index",
            "gate1_index",
            "gate2_index",
            "gate1_voltage_v",
            "gate2_voltage_v",
            "gate1_current_a",
            "gate2_current_a",
            "elapsed_s",
            "gate1_compliance_hit",
            "gate2_compliance_hit",
            "lockin_x_v",
            "lockin_y_v",
            "lockin_r_v",
            "lockin_theta_deg",
        }
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{path} is not a dual-gate lock-in points CSV; missing {sorted(missing)}")
        for row in reader:
            rows.append(
                {
                    "index": int(row["index"]),
                    "gate1_index": int(row["gate1_index"]),
                    "gate2_index": int(row["gate2_index"]),
                    "gate1_voltage_v": float(row["gate1_voltage_v"]),
                    "gate2_voltage_v": float(row["gate2_voltage_v"]),
                    "gate1_current_a": float(row["gate1_current_a"]),
                    "gate2_current_a": float(row["gate2_current_a"]),
                    "elapsed_s": float(row["elapsed_s"]),
                    "gate1_compliance_hit": parse_bool(row["gate1_compliance_hit"]),
                    "gate2_compliance_hit": parse_bool(row["gate2_compliance_hit"]),
                    "lockin_x_v": parse_optional_float(row["lockin_x_v"]),
                    "lockin_y_v": parse_optional_float(row["lockin_y_v"]),
                    "lockin_r_v": parse_optional_float(row["lockin_r_v"]),
                    "lockin_theta_deg": parse_optional_float(row["lockin_theta_deg"]),
                    "source_drain_excitation_v": parse_optional_float(row.get("source_drain_excitation_v", "")),
                    "source_drain_nominal_current_a": parse_optional_float(
                        row.get("source_drain_nominal_current_a", "")
                    ),
                    "lockin_resistance_ohm": parse_optional_float(row.get("lockin_resistance_ohm", "")),
                    "lockin_conductance_s": parse_optional_float(row.get("lockin_conductance_s", "")),
                }
            )
    return rows


def audit_dual_gate_lockin_run(
    run_dir: str | Path,
    require_lockin_settings: bool = True,
) -> DualGateLockInAcceptance:
    path = Path(run_dir)
    metadata = read_dual_gate_lockin_metadata(path)
    issues: list[DualGateLockInAcceptanceIssue] = []
    measurement_type = metadata.get("measurement_type")
    completed = metadata.get("completed")
    points_written = _optional_int(metadata.get("points_written"))
    planned_points = _optional_int(metadata.get("planned_points"))
    remaining_points = _optional_int(metadata.get("remaining_points"))
    rows: list[dict[str, float | int | bool | None]] = []
    leakage = _gate_leakage_acceptance_stats(metadata, rows)

    if measurement_type != "dual_gate_lockin_sweep":
        issues.append(
            DualGateLockInAcceptanceIssue(
                "error",
                "measurement_type",
                f"expected dual_gate_lockin_sweep, got {measurement_type or 'missing'}",
            )
        )
    if completed is not True:
        issues.append(DualGateLockInAcceptanceIssue("error", "completed", "run did not complete cleanly"))
    if metadata.get("abort_class") != "completed":
        issues.append(
            DualGateLockInAcceptanceIssue(
                "error",
                "abort_class",
                f"expected completed, got {metadata.get('abort_class') or 'missing'}",
            )
        )
    if metadata.get("error_type") or metadata.get("error_message"):
        issues.append(
            DualGateLockInAcceptanceIssue(
                "error",
                "error",
                f"{metadata.get('error_type') or 'unknown'}: {metadata.get('error_message') or ''}".strip(),
            )
        )
    if points_written is None or planned_points is None:
        issues.append(DualGateLockInAcceptanceIssue("error", "point_count", "points_written/planned_points missing"))
    elif points_written != planned_points:
        issues.append(
            DualGateLockInAcceptanceIssue(
                "error",
                "point_count",
                f"points_written {points_written} != planned_points {planned_points}",
            )
        )
    if remaining_points not in {0, None}:
        issues.append(
            DualGateLockInAcceptanceIssue(
                "error",
                "remaining_points",
                f"expected 0 remaining points, got {remaining_points}",
            )
        )
    _audit_smu_readback(metadata, "gate1", issues)
    _audit_smu_readback(metadata, "gate2", issues)
    _audit_output_cleanup(metadata, "gate1", issues)
    _audit_output_cleanup(metadata, "gate2", issues)
    _audit_lockin_probe(metadata, issues)
    if require_lockin_settings:
        _audit_lockin_settings(metadata, issues)
    try:
        rows = read_dual_gate_lockin_points(path)
        csv_points = len(rows)
        leakage = _gate_leakage_acceptance_stats(metadata, rows)
    except Exception as exc:
        issues.append(DualGateLockInAcceptanceIssue("error", "points_csv", f"{type(exc).__name__}: {exc}"))
    else:
        if points_written is not None and csv_points != points_written:
            issues.append(
                DualGateLockInAcceptanceIssue(
                    "error",
                    "points_csv",
                    f"points.csv row count {csv_points} != metadata points_written {points_written}",
                )
            )
        _audit_gate_leakage_margin(leakage, rows, issues)
        _audit_planned_gate_grid(metadata, rows=rows, issues=issues)

    errors = [issue for issue in issues if issue.severity == "error"]
    return DualGateLockInAcceptance(
        run_dir=path,
        accepted=not errors,
        measurement_type=measurement_type,
        completed=completed,
        points_written=points_written,
        planned_points=planned_points,
        remaining_points=remaining_points,
        gate1_leakage_abs_max_a=leakage["gate1_leakage_abs_max_a"],
        gate2_leakage_abs_max_a=leakage["gate2_leakage_abs_max_a"],
        gate1_compliance_a=leakage["gate1_compliance_a"],
        gate2_compliance_a=leakage["gate2_compliance_a"],
        gate1_leakage_compliance_margin=leakage["gate1_leakage_compliance_margin"],
        gate2_leakage_compliance_margin=leakage["gate2_leakage_compliance_margin"],
        issues=tuple(issues),
    )


def format_dual_gate_lockin_acceptance(audit: DualGateLockInAcceptance) -> str:
    status = "PASS" if audit.accepted else "FAIL"
    lines = [
        f"Dual-gate lock-in acceptance: {status}",
        f"Run directory: {audit.run_dir}",
        f"Measurement type: {audit.measurement_type or 'n/a'}",
        f"Completed: {audit.completed}",
        f"Points: {audit.points_written if audit.points_written is not None else 'n/a'} / {audit.planned_points if audit.planned_points is not None else 'n/a'}",
        f"Remaining points: {audit.remaining_points if audit.remaining_points is not None else 'n/a'}",
        f"Gate1 leakage max: {fmt(audit.gate1_leakage_abs_max_a, ' A')}",
        f"Gate2 leakage max: {fmt(audit.gate2_leakage_abs_max_a, ' A')}",
        f"Gate1 leakage/compliance margin: {fmt(audit.gate1_leakage_compliance_margin, 'x')}",
        f"Gate2 leakage/compliance margin: {fmt(audit.gate2_leakage_compliance_margin, 'x')}",
    ]
    if audit.issues:
        lines.append("Issues:")
        for issue in audit.issues:
            lines.append(f"- [{issue.severity}] {issue.check}: {issue.message}")
    else:
        lines.append("Issues: none")
    return "\n".join(lines)


def scale_up_blocking_acceptance_issues(
    audit: DualGateLockInAcceptance,
) -> tuple[DualGateLockInAcceptanceIssue, ...]:
    """Warnings that are acceptable for review but unsafe for a broader scan."""

    return tuple(
        issue
        for issue in audit.issues
        if issue.severity == "warning" and issue.check in SCALE_UP_BLOCKING_ACCEPTANCE_WARNING_CHECKS
    )


def format_scale_up_blocking_acceptance_issues(
    issues: tuple[DualGateLockInAcceptanceIssue, ...],
) -> str:
    lines = ["Scale-up blocking acceptance warning(s):"]
    for issue in issues:
        lines.append(f"- [{issue.severity}] {issue.check}: {issue.message}")
    lines.append("Repeat a limited run or fix the gate leakage margin before increasing the scan size.")
    return "\n".join(lines)


def write_dual_gate_lockin_acceptance_report(
    run_dir: str | Path,
    output_path: str | Path | None = None,
    require_lockin_settings: bool = True,
) -> Path:
    path = Path(run_dir)
    output = Path(output_path) if output_path is not None else path / "dual_gate_lockin_acceptance.md"
    audit = audit_dual_gate_lockin_run(path, require_lockin_settings=require_lockin_settings)
    output.write_text(format_dual_gate_lockin_acceptance(audit) + "\n", encoding="utf-8")
    return output


def audit_dual_gate_lockin_scale_up(
    previous_run: str | Path,
    candidate_recipe: DualGateLockInRecipe,
) -> DualGateLockInScaleUpAudit:
    previous_path = Path(previous_run)
    metadata = read_dual_gate_lockin_metadata(previous_path)
    previous_recipe = metadata.get("recipe") or {}
    candidate = candidate_recipe.model_dump(mode="json")
    candidate_grid = planned_dual_gate_lockin_grid(candidate_recipe)
    previous_grid = metadata.get("planned_gate_grid")
    issues: list[DualGateLockInScaleUpIssue] = []

    if metadata.get("measurement_type") != "dual_gate_lockin_sweep":
        issues.append(
            DualGateLockInScaleUpIssue(
                "error",
                "measurement_type",
                f"expected previous dual_gate_lockin_sweep, got {metadata.get('measurement_type') or 'missing'}",
            )
        )
    _compare_recipe_section(previous_recipe, candidate, "measurement_geometry", issues)
    _compare_recipe_section(previous_recipe, candidate, "topology", issues)
    _compare_recipe_section(previous_recipe, candidate, "lockin", issues)
    _compare_smu_section(previous_recipe, candidate, "gate1_instrument", issues)
    _compare_smu_section(previous_recipe, candidate, "gate2_instrument", issues)
    _compare_gate_sweep_policy(previous_recipe, candidate, "gate1_sweep", issues)
    _compare_gate_sweep_policy(previous_recipe, candidate, "gate2_sweep", issues)
    if not isinstance(previous_grid, list) or not previous_grid:
        issues.append(
            DualGateLockInScaleUpIssue(
                "error",
                "planned_gate_grid",
                "accepted previous run lacks planned_gate_grid metadata; rerun the limited scan with the current code",
            )
        )
    else:
        _check_previous_grid_subset(previous_grid, candidate_grid, issues)

    errors = [issue for issue in issues if issue.severity == "error"]
    return DualGateLockInScaleUpAudit(
        previous_run_dir=previous_path,
        compatible=not errors,
        previous_points=_optional_int(metadata.get("planned_points")),
        candidate_points=len(candidate_grid),
        previous_grid_signature=metadata.get("planned_gate_grid_signature"),
        issues=tuple(issues),
    )


def format_dual_gate_lockin_scale_up_audit(audit: DualGateLockInScaleUpAudit) -> str:
    status = "PASS" if audit.compatible else "FAIL"
    lines = [
        f"Dual-gate lock-in scale-up compatibility: {status}",
        f"Previous run directory: {audit.previous_run_dir}",
        f"Previous points: {audit.previous_points if audit.previous_points is not None else 'n/a'}",
        f"Candidate points: {audit.candidate_points}",
        f"Previous grid signature: {audit.previous_grid_signature or 'n/a'}",
    ]
    if audit.issues:
        lines.append("Issues:")
        for issue in audit.issues:
            lines.append(f"- [{issue.severity}] {issue.check}: {issue.message}")
    else:
        lines.append("Issues: none")
    return "\n".join(lines)


def _compare_recipe_section(
    previous_recipe: dict[str, Any],
    candidate_recipe: dict[str, Any],
    section: str,
    issues: list[DualGateLockInScaleUpIssue],
) -> None:
    if previous_recipe.get(section) != candidate_recipe.get(section):
        issues.append(
            DualGateLockInScaleUpIssue(
                "error",
                section,
                f"candidate {section} differs from accepted previous run",
            )
        )


def _compare_smu_section(
    previous_recipe: dict[str, Any],
    candidate_recipe: dict[str, Any],
    section: str,
    issues: list[DualGateLockInScaleUpIssue],
) -> None:
    keys = ["id", "address", "terminal", "voltage_range_v", "current_range_a", "nplc", "source_delay_s"]
    previous = previous_recipe.get(section) or {}
    candidate = candidate_recipe.get(section) or {}
    mismatches = [key for key in keys if previous.get(key) != candidate.get(key)]
    if mismatches:
        issues.append(
            DualGateLockInScaleUpIssue(
                "error",
                section,
                f"candidate {section} differs in {', '.join(mismatches)}",
            )
        )


def _compare_gate_sweep_policy(
    previous_recipe: dict[str, Any],
    candidate_recipe: dict[str, Any],
    section: str,
    issues: list[DualGateLockInScaleUpIssue],
) -> None:
    previous = previous_recipe.get(section) or {}
    candidate = candidate_recipe.get(section) or {}
    if previous.get("current_compliance_a") != candidate.get("current_compliance_a"):
        issues.append(
            DualGateLockInScaleUpIssue(
                "error",
                section,
                f"candidate {section}.current_compliance_a differs from accepted previous run",
            )
        )
    previous_settle = previous.get("settle_s")
    candidate_settle = candidate.get("settle_s")
    try:
        if previous_settle is not None and candidate_settle is not None and float(candidate_settle) < float(previous_settle):
            issues.append(
                DualGateLockInScaleUpIssue(
                    "error",
                    section,
                    f"candidate {section}.settle_s is shorter than accepted previous run",
                )
            )
    except (TypeError, ValueError):
        issues.append(DualGateLockInScaleUpIssue("error", section, f"candidate {section}.settle_s is invalid"))


def _check_previous_grid_subset(
    previous_grid: list[Any],
    candidate_grid: list[dict[str, float | int]],
    issues: list[DualGateLockInScaleUpIssue],
) -> None:
    candidate_pairs = {
        (_rounded_grid_voltage(point["gate1_voltage_v"]), _rounded_grid_voltage(point["gate2_voltage_v"]))
        for point in candidate_grid
    }
    missing = []
    for point in previous_grid:
        try:
            pair = (_rounded_grid_voltage(point["gate1_voltage_v"]), _rounded_grid_voltage(point["gate2_voltage_v"]))
        except (KeyError, TypeError, ValueError):
            issues.append(DualGateLockInScaleUpIssue("error", "planned_gate_grid", "previous planned grid is malformed"))
            return
        if pair not in candidate_pairs:
            missing.append(pair)
    if missing:
        preview = ", ".join(f"({gate1:g}, {gate2:g})" for gate1, gate2 in missing[:4])
        issues.append(
            DualGateLockInScaleUpIssue(
                "error",
                "planned_gate_grid",
                f"candidate grid does not include {len(missing)} previous accepted point(s): {preview}",
            )
        )


def _rounded_grid_voltage(value: Any) -> float:
    return round(float(value), 12)


def _gate_leakage_acceptance_stats(
    metadata: dict[str, Any],
    rows: list[dict[str, float | int | bool | None]],
) -> dict[str, float | None]:
    recipe = metadata.get("recipe") or {}
    gate1_compliance = _optional_float(((recipe.get("gate1_sweep") or {}).get("current_compliance_a")))
    gate2_compliance = _optional_float(((recipe.get("gate2_sweep") or {}).get("current_compliance_a")))
    gate1_max = max((abs(float(row["gate1_current_a"])) for row in rows), default=None)
    gate2_max = max((abs(float(row["gate2_current_a"])) for row in rows), default=None)
    return {
        "gate1_leakage_abs_max_a": gate1_max,
        "gate2_leakage_abs_max_a": gate2_max,
        "gate1_compliance_a": gate1_compliance,
        "gate2_compliance_a": gate2_compliance,
        "gate1_leakage_compliance_margin": _leakage_margin(gate1_max, gate1_compliance),
        "gate2_leakage_compliance_margin": _leakage_margin(gate2_max, gate2_compliance),
    }


def _audit_gate_leakage_margin(
    leakage: dict[str, float | None],
    rows: list[dict[str, float | int | bool | None]],
    issues: list[DualGateLockInAcceptanceIssue],
) -> None:
    if any(row["gate1_compliance_hit"] for row in rows):
        issues.append(DualGateLockInAcceptanceIssue("error", "gate1_leakage", "gate1 compliance hit appears in points.csv"))
    if any(row["gate2_compliance_hit"] for row in rows):
        issues.append(DualGateLockInAcceptanceIssue("error", "gate2_leakage", "gate2 compliance hit appears in points.csv"))
    for role in ["gate1", "gate2"]:
        leakage_max = leakage[f"{role}_leakage_abs_max_a"]
        compliance = leakage[f"{role}_compliance_a"]
        margin = leakage[f"{role}_leakage_compliance_margin"]
        if leakage_max is None:
            issues.append(DualGateLockInAcceptanceIssue("error", f"{role}_leakage", "leakage current data missing"))
            continue
        if compliance is None:
            issues.append(DualGateLockInAcceptanceIssue("warning", f"{role}_leakage", "compliance unavailable; margin not computed"))
            continue
        if leakage_max > compliance:
            issues.append(
                DualGateLockInAcceptanceIssue(
                    "error",
                    f"{role}_leakage",
                    f"max leakage {leakage_max:g} A exceeds compliance {compliance:g} A",
                )
            )
        elif margin is not None and margin < 10:
            issues.append(
                DualGateLockInAcceptanceIssue(
                    "warning",
                    f"{role}_leakage_margin",
                    f"leakage/compliance margin is {margin:g}x; review before broader scans",
                )
            )


def _leakage_margin(leakage_max: float | None, compliance: float | None) -> float | None:
    if leakage_max is None or compliance is None:
        return None
    if leakage_max == 0:
        return float("inf")
    return compliance / leakage_max


def _audit_smu_readback(
    metadata: dict[str, Any],
    role: str,
    issues: list[DualGateLockInAcceptanceIssue],
) -> None:
    configured = metadata.get(f"configured_{role}_smu") or {}
    check = metadata.get(f"configured_{role}_smu_readback_check")
    if not isinstance(check, dict):
        issues.append(DualGateLockInAcceptanceIssue("error", f"{role}_smu_readback", "readback check missing"))
        return
    if check.get("available") is not True:
        issues.append(DualGateLockInAcceptanceIssue("error", f"{role}_smu_readback", "readback unavailable"))
    if check.get("matched") is not True:
        failed = [item for item in check.get("checks", []) if not item.get("matched")]
        details = "; ".join(
            f"{item.get('field')} expected {item.get('expected')} got {item.get('actual')}" for item in failed[:4]
        )
        issues.append(
            DualGateLockInAcceptanceIssue(
                "error",
                f"{role}_smu_readback",
                details or "readback did not match expected source configuration",
            )
        )
    if configured.get("nplc") is None:
        issues.append(
            DualGateLockInAcceptanceIssue(
                "warning",
                f"{role}_nplc",
                "NPLC was not explicit in the recipe; set it deliberately before hardware scans",
            )
        )


def _audit_output_cleanup(
    metadata: dict[str, Any],
    role: str,
    issues: list[DualGateLockInAcceptanceIssue],
) -> None:
    state = (metadata.get("output_state") or {}).get(role) or {}
    if state.get("enabled") is True:
        issues.append(DualGateLockInAcceptanceIssue("error", f"{role}_output", "metadata still marks output enabled"))
    if state.get("off_after_run") is not True:
        issues.append(DualGateLockInAcceptanceIssue("error", f"{role}_output", "output-off cleanup not confirmed"))
    if state.get("zero_before_off_succeeded") is not True:
        issues.append(DualGateLockInAcceptanceIssue("error", f"{role}_zero", "0 V before output-off not confirmed"))
    last_command = state.get("last_commanded_voltage_v")
    try:
        if last_command is None or abs(float(last_command)) > 1e-12:
            issues.append(
                DualGateLockInAcceptanceIssue(
                    "error",
                    f"{role}_zero",
                    f"last commanded voltage after cleanup is {last_command}, expected 0 V",
                )
            )
    except (TypeError, ValueError):
        issues.append(DualGateLockInAcceptanceIssue("error", f"{role}_zero", "last commanded voltage is invalid"))


def _audit_lockin_probe(metadata: dict[str, Any], issues: list[DualGateLockInAcceptanceIssue]) -> None:
    probe = metadata.get("lockin_probe")
    if not isinstance(probe, dict):
        issues.append(DualGateLockInAcceptanceIssue("error", "lockin_probe", "lock-in probe missing"))
        return
    if not probe.get("idn"):
        issues.append(DualGateLockInAcceptanceIssue("error", "lockin_probe", "lock-in IDN missing"))
    for field in ["error_status", "lia_status"]:
        if field in probe and str(probe.get(field)).strip() not in {"0", "+0"}:
            issues.append(
                DualGateLockInAcceptanceIssue(
                    "error",
                    field,
                    f"SR860 {field} is {probe.get(field)}, expected 0",
                )
            )


def _audit_lockin_settings(metadata: dict[str, Any], issues: list[DualGateLockInAcceptanceIssue]) -> None:
    recipe = metadata.get("recipe") or {}
    lockin = recipe.get("lockin") or {}
    checks = compare_lockin_settings(lockin, metadata.get("lockin_probe"))
    if not checks:
        issues.append(DualGateLockInAcceptanceIssue("warning", "lockin_settings", "no expected SR860 settings declared"))
        return
    if not lockin_settings_ok(checks):
        failed = [check for check in checks if not check.ok]
        details = "; ".join(
            f"{check.field} expected {check.expected} got {check.actual if check.actual is not None else 'missing'}"
            for check in failed[:4]
        )
        issues.append(DualGateLockInAcceptanceIssue("error", "lockin_settings", details))


def _audit_planned_gate_grid(
    metadata: dict[str, Any],
    rows: list[dict[str, float | int | bool | None]],
    issues: list[DualGateLockInAcceptanceIssue],
) -> None:
    grid = metadata.get("planned_gate_grid")
    signature = metadata.get("planned_gate_grid_signature")
    algorithm = metadata.get("planned_gate_grid_signature_algorithm")
    if not isinstance(grid, list) or not signature:
        issues.append(
            DualGateLockInAcceptanceIssue(
                "warning",
                "planned_gate_grid",
                "planned gate grid/signature missing; rerun with newer metadata before relying on resume comparisons",
            )
        )
        return
    if algorithm != "sha256_json_v1":
        issues.append(
            DualGateLockInAcceptanceIssue(
                "error",
                "planned_gate_grid",
                f"unsupported signature algorithm {algorithm or 'missing'}",
            )
        )
        return
    expected_signature = _planned_gate_grid_signature(grid)
    if str(signature) != expected_signature:
        issues.append(
            DualGateLockInAcceptanceIssue(
                "error",
                "planned_gate_grid",
                "planned gate grid signature does not match saved grid",
            )
        )
    if len(grid) != len(rows):
        issues.append(
            DualGateLockInAcceptanceIssue(
                "error",
                "planned_gate_grid",
                f"planned grid length {len(grid)} != points.csv row count {len(rows)}",
            )
        )
        return
    for index, (planned, row) in enumerate(zip(grid, rows)):
        try:
            planned_index = int(planned["index"])
            planned_gate1_index = int(planned["gate1_index"])
            planned_gate2_index = int(planned["gate2_index"])
            planned_gate1_v = float(planned["gate1_voltage_v"])
            planned_gate2_v = float(planned["gate2_voltage_v"])
        except (KeyError, TypeError, ValueError):
            issues.append(
                DualGateLockInAcceptanceIssue(
                    "error",
                    "planned_gate_grid",
                    f"planned grid entry #{index} is malformed",
                )
            )
            return
        if (
            planned_index != int(row["index"])
            or planned_gate1_index != int(row["gate1_index"])
            or planned_gate2_index != int(row["gate2_index"])
            or abs(planned_gate1_v - float(row["gate1_voltage_v"])) > 1e-12
            or abs(planned_gate2_v - float(row["gate2_voltage_v"])) > 1e-12
        ):
            issues.append(
                DualGateLockInAcceptanceIssue(
                    "error",
                    "planned_gate_grid",
                    f"points.csv row #{index} does not match planned grid entry",
                )
            )
            return


def _planned_gate_grid_signature(grid: list[Any]) -> str:
    payload = json.dumps(grid, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def summarize_dual_gate_lockin_run(run_dir: str | Path) -> DualGateLockInSummary:
    path = Path(run_dir)
    metadata = read_dual_gate_lockin_metadata(path)
    recipe = metadata.get("recipe") or {}
    topology = recipe.get("topology") or {}
    points = read_dual_gate_lockin_points(path)
    gate1_voltages = [float(point["gate1_voltage_v"]) for point in points]
    gate2_voltages = [float(point["gate2_voltage_v"]) for point in points]
    gate1_currents = [float(point["gate1_current_a"]) for point in points]
    gate2_currents = [float(point["gate2_current_a"]) for point in points]
    lockin_r = [point["lockin_r_v"] for point in points if point["lockin_r_v"] is not None]
    lockin_resistance = [
        point["lockin_resistance_ohm"] for point in points if point.get("lockin_resistance_ohm") is not None
    ]
    lockin_conductance = [
        point["lockin_conductance_s"] for point in points if point.get("lockin_conductance_s") is not None
    ]
    lockin_theta = [point["lockin_theta_deg"] for point in points if point["lockin_theta_deg"] is not None]
    return DualGateLockInSummary(
        run_dir=path,
        measurement_name=metadata.get("measurement_name") or path.name,
        measurement_geometry=format_geometry(recipe.get("measurement_geometry") or {}),
        topology_layout=topology.get("device_layout"),
        lockin_voltage_contacts=format_contact_list(topology.get("lockin_input_contacts") or []),
        excitation_contacts=format_contact_list(topology.get("excitation_contacts") or []),
        completed=metadata.get("completed"),
        points=len(points),
        gate1_points=len({float(point["gate1_voltage_v"]) for point in points}),
        gate2_points=len({float(point["gate2_voltage_v"]) for point in points}),
        gate1_voltage_min_v=min(gate1_voltages) if gate1_voltages else None,
        gate1_voltage_max_v=max(gate1_voltages) if gate1_voltages else None,
        gate2_voltage_min_v=min(gate2_voltages) if gate2_voltages else None,
        gate2_voltage_max_v=max(gate2_voltages) if gate2_voltages else None,
        gate1_leakage_abs_max_a=max((abs(value) for value in gate1_currents), default=None),
        gate2_leakage_abs_max_a=max((abs(value) for value in gate2_currents), default=None),
        lockin_r_min_v=min(lockin_r) if lockin_r else None,
        lockin_r_max_v=max(lockin_r) if lockin_r else None,
        lockin_resistance_min_ohm=min(lockin_resistance) if lockin_resistance else None,
        lockin_resistance_max_ohm=max(lockin_resistance) if lockin_resistance else None,
        lockin_conductance_min_s=min(lockin_conductance) if lockin_conductance else None,
        lockin_conductance_max_s=max(lockin_conductance) if lockin_conductance else None,
        lockin_theta_min_deg=min(lockin_theta) if lockin_theta else None,
        lockin_theta_max_deg=max(lockin_theta) if lockin_theta else None,
        error_type=metadata.get("error_type"),
        error_message=metadata.get("error_message"),
    )


def format_dual_gate_lockin_summary(summary: DualGateLockInSummary) -> str:
    lines = [
        f"Dual-gate lock-in run: {summary.run_dir}",
        f"Measurement: {summary.measurement_name}",
        f"Geometry: {summary.measurement_geometry}",
        f"Topology layout: {summary.topology_layout or 'n/a'}",
        f"Lock-in voltage contacts: {summary.lockin_voltage_contacts}",
        f"Excitation contacts: {summary.excitation_contacts}",
        f"Completed: {summary.completed}",
        f"Points: {summary.points}",
        f"Gate1 points: {summary.gate1_points}",
        f"Gate2 points: {summary.gate2_points}",
        f"Gate1 voltage range: {fmt(summary.gate1_voltage_min_v, ' V')} to {fmt(summary.gate1_voltage_max_v, ' V')}",
        f"Gate2 voltage range: {fmt(summary.gate2_voltage_min_v, ' V')} to {fmt(summary.gate2_voltage_max_v, ' V')}",
        f"Max abs gate1 leakage: {fmt(summary.gate1_leakage_abs_max_a, ' A')}",
        f"Max abs gate2 leakage: {fmt(summary.gate2_leakage_abs_max_a, ' A')}",
        f"Lock-in R range: {fmt(summary.lockin_r_min_v, ' V')} to {fmt(summary.lockin_r_max_v, ' V')}",
        f"Lock-in resistance range: {fmt(summary.lockin_resistance_min_ohm, ' ohm')} to {fmt(summary.lockin_resistance_max_ohm, ' ohm')}",
        f"Lock-in conductance range: {fmt(summary.lockin_conductance_min_s, ' S')} to {fmt(summary.lockin_conductance_max_s, ' S')}",
        f"Lock-in theta range: {fmt(summary.lockin_theta_min_deg, ' deg')} to {fmt(summary.lockin_theta_max_deg, ' deg')}",
    ]
    if summary.error_type:
        lines.append(f"Error: {summary.error_type}: {summary.error_message}")
    return "\n".join(lines)


def dual_gate_lockin_stats_rows(run_dir: str | Path) -> list[dict[str, Any]]:
    points = read_dual_gate_lockin_points(run_dir)
    rows = []
    gate_pairs = sorted({(float(point["gate1_voltage_v"]), float(point["gate2_voltage_v"])) for point in points})
    for index, (gate1_voltage_v, gate2_voltage_v) in enumerate(gate_pairs):
        group = [
            point
            for point in points
            if float(point["gate1_voltage_v"]) == gate1_voltage_v and float(point["gate2_voltage_v"]) == gate2_voltage_v
        ]
        lockin_r = [float(point["lockin_r_v"]) for point in group if point["lockin_r_v"] is not None]
        lockin_resistance = [
            float(point["lockin_resistance_ohm"]) for point in group if point.get("lockin_resistance_ohm") is not None
        ]
        lockin_conductance = [
            float(point["lockin_conductance_s"]) for point in group if point.get("lockin_conductance_s") is not None
        ]
        gate1_currents = [float(point["gate1_current_a"]) for point in group]
        gate2_currents = [float(point["gate2_current_a"]) for point in group]
        rows.append(
            {
                "gate_pair_index": index,
                "gate1_voltage_v": gate1_voltage_v,
                "gate2_voltage_v": gate2_voltage_v,
                "points": len(group),
                "lockin_r_mean_v": mean(lockin_r),
                "lockin_r_min_v": min(lockin_r) if lockin_r else None,
                "lockin_r_max_v": max(lockin_r) if lockin_r else None,
                "lockin_resistance_mean_ohm": mean(lockin_resistance),
                "lockin_resistance_min_ohm": min(lockin_resistance) if lockin_resistance else None,
                "lockin_resistance_max_ohm": max(lockin_resistance) if lockin_resistance else None,
                "lockin_conductance_mean_s": mean(lockin_conductance),
                "lockin_conductance_min_s": min(lockin_conductance) if lockin_conductance else None,
                "lockin_conductance_max_s": max(lockin_conductance) if lockin_conductance else None,
                "gate1_current_abs_max_a": max((abs(value) for value in gate1_currents), default=None),
                "gate2_current_abs_max_a": max((abs(value) for value in gate2_currents), default=None),
            }
        )
    return rows


def write_dual_gate_lockin_stats_csv(run_dir: str | Path, output_path: str | Path | None = None) -> Path:
    path = Path(run_dir)
    output = Path(output_path) if output_path is not None else path / "dual_gate_lockin_stats.csv"
    fieldnames = [
        "gate_pair_index",
        "gate1_voltage_v",
        "gate2_voltage_v",
        "points",
        "lockin_r_mean_v",
        "lockin_r_min_v",
        "lockin_r_max_v",
        "lockin_resistance_mean_ohm",
        "lockin_resistance_min_ohm",
        "lockin_resistance_max_ohm",
        "lockin_conductance_mean_s",
        "lockin_conductance_min_s",
        "lockin_conductance_max_s",
        "gate1_current_abs_max_a",
        "gate2_current_abs_max_a",
    ]
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in dual_gate_lockin_stats_rows(path):
            writer.writerow(row)
    return output


def write_dual_gate_lockin_heatmap_svg(run_dir: str | Path, output_path: str | Path | None = None) -> Path:
    path = Path(run_dir)
    rows = dual_gate_lockin_stats_rows(path)
    if not rows:
        raise ValueError(f"No points to plot in {path}")
    output = Path(output_path) if output_path is not None else path / "dual_gate_lockin_heatmap.svg"
    summary = summarize_dual_gate_lockin_run(path)
    gate1_values = sorted({float(row["gate1_voltage_v"]) for row in rows})
    gate2_values = sorted({float(row["gate2_voltage_v"]) for row in rows})
    lockin_values = [float(row["lockin_r_mean_v"]) for row in rows if row["lockin_r_mean_v"] is not None]
    max_abs_signal = max((abs(value) for value in lockin_values), default=1.0) or 1.0
    by_coord = {
        (float(row["gate1_voltage_v"]), float(row["gate2_voltage_v"])): float(row["lockin_r_mean_v"] or 0.0)
        for row in rows
    }

    width, height = 820, 560
    left, right, top, bottom = 104, 130, 82, 78
    plot_w = width - left - right
    plot_h = height - top - bottom
    cell_w = plot_w / max(1, len(gate2_values))
    cell_h = plot_h / max(1, len(gate1_values))
    cells = []
    for gate1_pos, gate1_voltage_v in enumerate(gate1_values):
        y = top + (len(gate1_values) - gate1_pos - 1) * cell_h
        for gate2_pos, gate2_voltage_v in enumerate(gate2_values):
            x = left + gate2_pos * cell_w
            signal = by_coord.get((gate1_voltage_v, gate2_voltage_v), 0.0)
            cells.append(
                f'<rect x="{x:.2f}" y="{y:.2f}" width="{cell_w + 0.2:.2f}" height="{cell_h + 0.2:.2f}" fill="{current_color(signal, max_abs_signal)}" />'
            )

    title = escape(summary.measurement_name)
    subtitle = f"completed={summary.completed}, points={summary.points}, lock-in R={fmt(summary.lockin_r_min_v, ' V')} to {fmt(summary.lockin_r_max_v, ' V')}"
    legend = legend_svg(left + plot_w + 28, top, plot_h)
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <rect width="100%" height="100%" fill="#ffffff" />
  <text x="{left}" y="30" font-family="Arial, sans-serif" font-size="18" fill="#111827">{title}</text>
  <text x="{left}" y="56" font-family="Arial, sans-serif" font-size="13" fill="#374151">{escape(subtitle)}</text>
  <rect x="{left}" y="{top}" width="{plot_w}" height="{plot_h}" fill="#f9fafb" stroke="#9ca3af" />
  {''.join(cells)}
  <rect x="{left}" y="{top}" width="{plot_w}" height="{plot_h}" fill="none" stroke="#374151" />
  {legend}
  <text x="{left + plot_w / 2 - 42:.2f}" y="{height - 22}" font-family="Arial, sans-serif" font-size="14" fill="#111827">Gate2 voltage (V)</text>
  <text x="20" y="{top + plot_h / 2 + 42:.2f}" transform="rotate(-90 20 {top + plot_h / 2 + 42:.2f})" font-family="Arial, sans-serif" font-size="14" fill="#111827">Gate1 voltage (V)</text>
  <text x="{left}" y="{height - 48}" font-family="Arial, sans-serif" font-size="12" fill="#4b5563">{gate2_values[0]:.6g} V</text>
  <text x="{left + plot_w - 70}" y="{height - 48}" font-family="Arial, sans-serif" font-size="12" fill="#4b5563">{gate2_values[-1]:.6g} V</text>
  <text x="36" y="{top + 6}" font-family="Arial, sans-serif" font-size="12" fill="#4b5563">{gate1_values[-1]:.6g} V</text>
  <text x="36" y="{top + plot_h}" font-family="Arial, sans-serif" font-size="12" fill="#4b5563">{gate1_values[0]:.6g} V</text>
  <text x="{left + plot_w + 48}" y="{top - 14}" font-family="Arial, sans-serif" font-size="12" fill="#111827">mean R</text>
  <text x="{left + plot_w + 56}" y="{top + plot_h + 22}" font-family="Arial, sans-serif" font-size="11" fill="#4b5563">+/-{max_abs_signal:.3g} V</text>
</svg>
'''
    output.write_text(svg, encoding="utf-8")
    return output


def write_dual_gate_lockin_report(run_dir: str | Path, output_path: str | Path | None = None) -> Path:
    path = Path(run_dir)
    output = Path(output_path) if output_path is not None else path / "dual_gate_lockin_report.md"
    output.write_text(format_dual_gate_lockin_report(path), encoding="utf-8")
    return output


def format_dual_gate_lockin_report(run_dir: str | Path) -> str:
    path = Path(run_dir)
    metadata = read_dual_gate_lockin_metadata(path)
    recipe = metadata.get("recipe") or {}
    experiment = recipe.get("experiment") or {}
    measurement_geometry = recipe.get("measurement_geometry") or {}
    lockin = recipe.get("lockin") or {}
    topology = recipe.get("topology") or {}
    summary = summarize_dual_gate_lockin_run(path)
    stats_rows = dual_gate_lockin_stats_rows(path)
    lines = [
        f"# {summary.measurement_name}",
        "",
        "## Summary",
        "",
        f"- Run directory: `{path}`",
        f"- Completed: {summary.completed}",
        f"- Points: {summary.points}",
        f"- Gate1 points: {summary.gate1_points}",
        f"- Gate2 points: {summary.gate2_points}",
        f"- Lock-in R range: {fmt(summary.lockin_r_min_v, ' V')} to {fmt(summary.lockin_r_max_v, ' V')}",
        f"- Lock-in resistance range: {fmt(summary.lockin_resistance_min_ohm, ' ohm')} to {fmt(summary.lockin_resistance_max_ohm, ' ohm')}",
        f"- Lock-in conductance range: {fmt(summary.lockin_conductance_min_s, ' S')} to {fmt(summary.lockin_conductance_max_s, ' S')}",
        f"- Max abs gate1 leakage: {fmt(summary.gate1_leakage_abs_max_a, ' A')}",
        f"- Max abs gate2 leakage: {fmt(summary.gate2_leakage_abs_max_a, ' A')}",
        "",
        "## Measurement Context",
        "",
        *[f"- {line}" for line in format_lockin_contact_context(measurement_geometry, lockin, topology)],
        "",
        "## Experiment",
        "",
        f"- Sample: {experiment.get('sample_id') or 'n/a'}",
        f"- Device: {experiment.get('device_id') or 'n/a'}",
        f"- Tags: {', '.join(experiment.get('tags') or []) or 'none'}",
        "",
        "## Lock-In",
        "",
        f"- Instrument: {lockin.get('id') or 'n/a'} @ `{lockin.get('address') or 'n/a'}`",
        f"- Channels: {', '.join(lockin.get('channels') or []) or 'n/a'}",
        f"- Read timing: {lockin.get('read_timing') or 'n/a'}",
        f"- Source-drain excitation: {fmt(metadata.get('source_drain_excitation_v'), ' V')}",
        f"- Nominal source-drain current: {fmt(metadata.get('source_drain_nominal_current_a'), ' A')}",
        "",
        "## Gate-Pair Statistics",
        "",
        "| Gate1 V | Gate2 V | Points | Mean Lock-in R | Mean Resistance | Mean Conductance | Gate1 I Abs Max | Gate2 I Abs Max |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in stats_rows:
        lines.append(
            (
                f"| {fmt(row['gate1_voltage_v'], ' V')} | {fmt(row['gate2_voltage_v'], ' V')} | {row['points']} | "
                f"{fmt(row['lockin_r_mean_v'], ' V')} | {fmt(row['lockin_resistance_mean_ohm'], ' ohm')} | "
                f"{fmt(row['lockin_conductance_mean_s'], ' S')} | {fmt(row['gate1_current_abs_max_a'], ' A')} | "
                f"{fmt(row['gate2_current_abs_max_a'], ' A')} |"
            )
        )
    if (path / "dual_gate_lockin_heatmap.svg").exists():
        lines.extend(["", "## Heatmap", "", "![Dual-gate lock-in heatmap](dual_gate_lockin_heatmap.svg)"])
    if "planned_points" in metadata or "abort_class" in metadata:
        last_index = metadata.get("last_completed_index")
        last_gate1 = metadata.get("last_completed_gate1_voltage_v")
        last_gate2 = metadata.get("last_completed_gate2_voltage_v")
        last_point = (
            "none"
            if last_index is None
            else f"#{last_index}, Vg1={fmt(last_gate1, ' V')}, Vg2={fmt(last_gate2, ' V')}"
        )
        lines.extend(
            [
                "",
                "## Recovery",
                "",
                f"- Abort class: {metadata.get('abort_class') or 'n/a'}",
                f"- Planned points: {metadata.get('planned_points') or 'n/a'}",
                f"- Points written: {metadata.get('points_written') or 0}",
                f"- Remaining points: {metadata.get('remaining_points') if metadata.get('remaining_points') is not None else 'n/a'}",
                f"- Last completed point: {last_point}",
                f"- Next point index: {metadata.get('next_point_index') if metadata.get('next_point_index') is not None else 'n/a'}",
                f"- Triggered limit: {metadata.get('triggered_limit') or 'none'}",
                f"- Outputs off after run: {metadata.get('outputs_off_after_run')}",
                f"- Resume policy: {metadata.get('resume_policy') or 'n/a'}",
                f"- Recommendation: {metadata.get('recovery_recommendation') or 'n/a'}",
            ]
        )
    if summary.error_type:
        lines.extend(["", "## Error", "", f"- Type: {summary.error_type}", f"- Message: {summary.error_message}"])
    return "\n".join(lines) + "\n"
