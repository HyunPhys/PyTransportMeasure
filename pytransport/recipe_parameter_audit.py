"""Directory-level measurement parameter audit for recipe YAML files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .measurement_parameters import measurement_parameter_audit_to_dict
from .method_registry import handler_for_measurement_type
from .recipes import load_four_terminal_dc_recipe, load_yaml


RECIPE_SUFFIXES = {".yaml", ".yml"}


def audit_recipe_parameter_directory(
    root: str | Path,
    *,
    recursive: bool = True,
) -> dict[str, Any]:
    root_path = Path(root)
    records = []
    for recipe_path in _recipe_paths(root_path, recursive=recursive):
        records.append(audit_recipe_parameter_file(recipe_path))
    ok = bool(records) and all(record["ok_for_hardware"] for record in records)
    return {
        "schema": "pytransport.recipe_parameter_audit.v1",
        "root": str(root_path),
        "recursive": recursive,
        "recipe_count": len(records),
        "ok_for_hardware": ok,
        "recipes": records,
    }


def audit_recipe_parameter_file(path: str | Path) -> dict[str, Any]:
    recipe_path = Path(path)
    try:
        measurement_type = infer_measurement_type_from_yaml(recipe_path)
        recipe = _load_recipe_for_audit(measurement_type, recipe_path)
        audit = measurement_parameter_audit_to_dict(recipe)
        return {
            "path": str(recipe_path),
            "measurement_type": measurement_type,
            "loaded": True,
            "ok_for_hardware": audit["ok_for_hardware"],
            "audit": audit,
            "error_type": None,
            "error_message": None,
        }
    except Exception as exc:
        return {
            "path": str(recipe_path),
            "measurement_type": None,
            "loaded": False,
            "ok_for_hardware": False,
            "audit": None,
            "error_type": type(exc).__name__,
            "error_message": str(exc),
        }


def infer_measurement_type_from_yaml(path: str | Path) -> str:
    data = load_yaml(Path(path))
    if "dc_sense_mode" in data or ("contacts" in data and "instrument" in data):
        return "dc_four_terminal"
    if "gate1_instrument" in data and "gate2_instrument" in data and "lockin" in data:
        return "dual_gate_lockin_sweep"
    if "source_instrument" in data and "lockin" in data and "bias_sweep" in data:
        return "ac_lockin_sweep"
    if "source_instrument" in data and "pulse" in data:
        return "pulse_measurement"
    if "drain_instrument" in data and "gate1_instrument" in data and "gate2_instrument" in data:
        return "dual_gate_sweep"
    if "drain_instrument" in data and "gate_instrument" in data:
        return "single_gate_sweep"
    if "instrument" in data and "sweep" in data:
        return "drain_iv"
    keys = ", ".join(sorted(str(key) for key in data))
    raise ValueError(f"cannot infer measurement type from recipe keys: {keys}")


def _load_recipe_for_audit(measurement_type: str, recipe_path: Path) -> Any:
    if measurement_type == "dc_four_terminal":
        return load_four_terminal_dc_recipe(recipe_path)
    return handler_for_measurement_type(measurement_type).load_recipe(recipe_path)


def format_recipe_parameter_directory_audit(payload: dict[str, Any]) -> str:
    lines = [
        "Recipe measurement parameter directory audit",
        f"Root: {payload['root']}",
        f"Recursive: {payload['recursive']}",
        f"Recipe count: {payload['recipe_count']}",
        f"Hardware-ready: {payload['ok_for_hardware']}",
        "",
        "| Recipe | Type | Loaded | Hardware-ready | Issues |",
        "| --- | --- | --- | --- | --- |",
    ]
    for record in payload["recipes"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{record['path']}`",
                    record.get("measurement_type") or "unknown",
                    str(record["loaded"]),
                    str(record["ok_for_hardware"]),
                    _record_issue_summary(record),
                ]
            )
            + " |"
        )
    if not payload["recipes"]:
        lines.append("| n/a | n/a | False | False | no recipe YAML files found |")
    lines.extend(
        [
            "",
            "Hardware-ready means every Keithley 2450 block declares NPLC, voltage range, and current range,",
            "and every SR860 block declares the required lock-in measurement settings and positive settle policy.",
        ]
    )
    return "\n".join(lines)


def write_recipe_parameter_directory_audit_json(payload: dict[str, Any], output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _recipe_paths(root: Path, *, recursive: bool) -> list[Path]:
    if root.is_file():
        return [root] if root.suffix.lower() in RECIPE_SUFFIXES else []
    if not root.exists():
        raise FileNotFoundError(root)
    pattern = "**/*" if recursive else "*"
    return sorted(path for path in root.glob(pattern) if path.is_file() and path.suffix.lower() in RECIPE_SUFFIXES)


def _record_issue_summary(record: dict[str, Any]) -> str:
    if not record["loaded"]:
        return f"{record['error_type']}: {record['error_message']}"
    audit = record.get("audit") or {}
    issues: list[str] = []
    for role in audit.get("smu", {}).get("roles", []):
        missing = role.get("missing_required_parameters") or []
        if missing:
            issues.append(f"{role.get('role')}: missing {', '.join(missing)}")
    for role in audit.get("lockin", {}).get("roles", []):
        missing = role.get("missing_required_parameters") or []
        role_issues = []
        if missing:
            role_issues.append(f"missing {', '.join(missing)}")
        if role.get("instrument_id") == "srs_sr860" and not role.get("settle_policy_ok"):
            role_issues.append("missing positive settle policy")
        if role_issues:
            issues.append(f"{role.get('role')}: {'; '.join(role_issues)}")
    return "PASS" if not issues else "<br>".join(issues)
