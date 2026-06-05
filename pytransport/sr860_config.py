"""Hardware-free SR860 configuration command review."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .lockin_settings import expected_lockin_setting_code
from .measurement_parameters import audit_lockin_hardware_parameters, lockin_hardware_parameter_audit_to_dict


@dataclass(frozen=True)
class SR860ConfigCommand:
    index: int
    field: str
    command: str
    query: str
    expected_readback: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SR860ConfigApplyStep:
    index: int
    field: str
    command: str
    query: str
    expected_readback: str
    actual_readback: str | None
    matched: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


SR860_COMMAND_SPECS: dict[str, tuple[str, str, str]] = {
    "reference_source": ("RSRC", "RSRC?", "set reference source"),
    "reference_frequency_hz": ("FREQ", "FREQ?", "set internal reference frequency"),
    "sine_output_amplitude_v": ("SLVL", "SLVL?", "set sine output amplitude"),
    "input_mode": ("IVMD", "IVMD?", "set voltage/current input mode"),
    "voltage_input": ("ISRC", "ISRC?", "set voltage input wiring"),
    "input_coupling": ("ICPL", "ICPL?", "set input coupling"),
    "input_grounding": ("IGND", "IGND?", "set input grounding"),
    "voltage_input_range_v": ("IRNG", "IRNG?", "set voltage input range"),
    "sensitivity_index": ("SCAL", "SCAL?", "set full-scale sensitivity"),
    "time_constant_index": ("OFLT", "OFLT?", "set low-pass time constant"),
    "filter_slope_db_per_oct": ("OFSL", "OFSL?", "set output filter slope"),
    "synchronous_filter": ("SYNC", "SYNC?", "set synchronous filter state"),
}


def build_sr860_config_commands(lockin: Any) -> list[SR860ConfigCommand]:
    data = _to_mapping(lockin)
    commands: list[SR860ConfigCommand] = []
    for field, (command_name, query, reason) in SR860_COMMAND_SPECS.items():
        value = data.get(field)
        if value is None:
            continue
        expected = _expected_sr860_readback(field, value)
        commands.append(
            SR860ConfigCommand(
                index=len(commands) + 1,
                field=field,
                command=f"{command_name} {expected}",
                query=query,
                expected_readback=expected,
                reason=reason,
            )
        )
    return commands


def review_sr860_config_commands(recipe: Any) -> dict[str, Any]:
    lockin = getattr(recipe, "lockin", None)
    if lockin is None:
        raise ValueError("recipe does not have a lockin block")
    lockin_audits = audit_lockin_hardware_parameters(recipe)
    audit_payload = lockin_hardware_parameter_audit_to_dict(lockin_audits)
    commands = build_sr860_config_commands(lockin)
    return {
        "schema": "pytransport.sr860_config_command_review.v1",
        "ok_for_hardware": bool(audit_payload["ok_for_hardware"]),
        "command_count": len(commands),
        "commands": [command.to_dict() for command in commands],
        "lockin_parameter_audit": audit_payload,
        "notes": [
            "Review only: this command does not communicate with VISA or write settings.",
            "Use the listed query after each write when an active SR860 configuration path is enabled.",
        ],
    }


def run_sr860_configure(
    recipe: Any,
    lockin: Any,
    *,
    recipe_path: str | Path | None = None,
    hardware_approval_note: str,
) -> dict[str, Any]:
    review = review_sr860_config_commands(recipe)
    commands = build_sr860_config_commands(getattr(recipe, "lockin"))
    payload: dict[str, Any] = {
        "schema": "pytransport.sr860_configure.v1",
        "recipe": None if recipe_path is None else str(Path(recipe_path)),
        "hardware_approval_note": hardware_approval_note,
        "review": review,
        "connected": False,
        "probe_before": None,
        "probe_after": None,
        "apply": None,
        "completed": False,
        "error_type": None,
        "error_message": None,
    }
    try:
        lockin.connect()
        payload["connected"] = True
        payload["probe_before"] = lockin.probe()
        if hasattr(lockin, "apply_config_commands"):
            payload["apply"] = lockin.apply_config_commands(commands)
        else:
            payload["apply"] = apply_sr860_config_commands(lockin, commands)
        payload["probe_after"] = lockin.probe()
        payload["completed"] = bool(payload["apply"]["matched"])
        return payload
    except Exception as exc:
        payload["error_type"] = type(exc).__name__
        payload["error_message"] = str(exc)
        return payload
    finally:
        close = getattr(lockin, "close", None)
        if close is not None:
            close()


def apply_sr860_config_commands(lockin: Any, commands: list[SR860ConfigCommand]) -> dict[str, Any]:
    steps: list[SR860ConfigApplyStep] = []
    for command in commands:
        lockin.write(command.command)
        actual = lockin.query(command.query)
        matched = sr860_readback_matches(command.field, command.expected_readback, actual)
        steps.append(
            SR860ConfigApplyStep(
                index=command.index,
                field=command.field,
                command=command.command,
                query=command.query,
                expected_readback=command.expected_readback,
                actual_readback=actual,
                matched=matched,
            )
        )
        if not matched:
            break
    return {
        "matched": bool(steps) and all(step.matched for step in steps),
        "steps": [step.to_dict() for step in steps],
    }


def sr860_readback_matches(field: str, expected_readback: str, actual: str | None) -> bool:
    if actual is None:
        return False
    actual_text = str(actual).strip()
    if field in {"reference_frequency_hz", "sine_output_amplitude_v"}:
        try:
            return abs(float(actual_text) - float(expected_readback)) <= max(1e-12, abs(float(expected_readback)) * 1e-6)
        except ValueError:
            return False
    return _normalize_sr860_token(actual_text) == _normalize_sr860_token(expected_readback)


def format_sr860_config_command_review(payload: dict[str, Any]) -> str:
    lines = [
        "SR860 configuration command review",
        f"Hardware-ready parameters: {payload['ok_for_hardware']}",
        f"Command count: {payload['command_count']}",
        "",
        "| # | Field | Write command | Readback query | Expected | Reason |",
        "| ---: | --- | --- | --- | --- | --- |",
    ]
    if not payload["commands"]:
        lines.append("| 0 | n/a | n/a | n/a | n/a | no declared SR860 settings |")
    for command in payload["commands"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(command["index"]),
                    command["field"],
                    f"`{command['command']}`",
                    f"`{command['query']}`",
                    command["expected_readback"],
                    command["reason"],
                ]
            )
            + " |"
        )
    lines.extend(["", *[f"- {note}" for note in payload.get("notes", [])]])
    return "\n".join(lines)


def format_sr860_configure_result(payload: dict[str, Any]) -> str:
    lines = [
        "SR860 guarded configure result",
        f"Completed: {payload.get('completed')}",
        f"Connected: {payload.get('connected')}",
        f"Approval note: {payload.get('hardware_approval_note')}",
    ]
    if payload.get("error_type"):
        lines.append(f"Error: {payload['error_type']}: {payload['error_message']}")
    apply_payload = payload.get("apply") if isinstance(payload.get("apply"), dict) else None
    if apply_payload is not None:
        lines.extend(
            [
                f"Readback matched: {apply_payload.get('matched')}",
                "",
                "| # | Field | Command | Query | Expected | Actual | Matched |",
                "| ---: | --- | --- | --- | --- | --- | --- |",
            ]
        )
        for step in apply_payload.get("steps", []):
            lines.append(
                "| "
                + " | ".join(
                    [
                        str(step.get("index")),
                        str(step.get("field")),
                        f"`{step.get('command')}`",
                        f"`{step.get('query')}`",
                        str(step.get("expected_readback")),
                        str(step.get("actual_readback")),
                        str(step.get("matched")),
                    ]
                )
                + " |"
            )
    return "\n".join(lines)


def check_sr860_configure_evidence(recipe: Any, payload: dict[str, Any]) -> dict[str, Any]:
    expected_commands = [command.to_dict() for command in build_sr860_config_commands(getattr(recipe, "lockin"))]
    review = payload.get("review") if isinstance(payload.get("review"), dict) else {}
    apply_payload = payload.get("apply") if isinstance(payload.get("apply"), dict) else {}
    steps = apply_payload.get("steps") if isinstance(apply_payload.get("steps"), list) else []
    checks = [
        _evidence_check("schema", payload.get("schema") == "pytransport.sr860_configure.v1", "payload schema is SR860 configure v1"),
        _evidence_check("completed", payload.get("completed") is True, "configure run completed successfully"),
        _evidence_check("review_ok", review.get("ok_for_hardware") is True, "embedded command review was hardware-ready"),
        _evidence_check(
            "review_commands_match_recipe",
            _command_lists_match(review.get("commands"), expected_commands),
            "embedded command review matches the current recipe",
        ),
        _evidence_check("apply_matched", apply_payload.get("matched") is True, "overall apply readback matched"),
        _evidence_check(
            "apply_step_count",
            len(steps) == len(expected_commands),
            "apply transcript has one step per expected command",
        ),
        _evidence_check(
            "apply_steps_match_recipe",
            _apply_steps_match_expected(steps, expected_commands),
            "apply transcript commands and expected readbacks match the current recipe",
        ),
        _evidence_check(
            "all_steps_matched",
            bool(steps) and all(isinstance(step, dict) and step.get("matched") is True for step in steps),
            "every SR860 write/readback step matched",
        ),
    ]
    return {
        "schema": "pytransport.sr860_configure_evidence_check.v1",
        "ok": all(check["passed"] for check in checks),
        "expected_command_count": len(expected_commands),
        "transcript_command_count": len(steps),
        "checks": checks,
    }


def format_sr860_configure_evidence_check(payload: dict[str, Any]) -> str:
    lines = [
        "SR860 configure evidence check",
        f"OK: {payload.get('ok')}",
        f"Expected commands: {payload.get('expected_command_count')}",
        f"Transcript commands: {payload.get('transcript_command_count')}",
        "",
    ]
    for check in payload.get("checks", []):
        mark = "PASS" if check.get("passed") else "FAIL"
        lines.append(f"- {check.get('name')}: {mark} ({check.get('message')})")
    return "\n".join(lines)


def load_sr860_configure_json(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"SR860 configure JSON must contain an object: {path}")
    return data


def write_sr860_configure_evidence_check_json(payload: dict[str, Any], output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def write_sr860_config_command_review_json(payload: dict[str, Any], output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def write_sr860_configure_json(payload: dict[str, Any], output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _expected_sr860_readback(field: str, value: Any) -> str:
    if field in {"reference_frequency_hz", "sine_output_amplitude_v"}:
        return f"{float(value):.12g}"
    code = expected_lockin_setting_code(field, value)
    if code is None:
        raise ValueError(f"cannot map SR860 setting {field}={value!r} to a command code")
    return code


def _to_mapping(lockin: Any) -> dict[str, Any]:
    if isinstance(lockin, dict):
        return lockin
    if hasattr(lockin, "model_dump"):
        return lockin.model_dump(mode="json")
    return {
        field: getattr(lockin, field, None)
        for field in SR860_COMMAND_SPECS
    }


def _normalize_sr860_token(value: str) -> str:
    return value.strip().strip('"').lower().replace("_", "").replace("-", "")


def _evidence_check(name: str, passed: bool, message: str) -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), "message": message}


def _command_lists_match(actual: Any, expected: list[dict[str, Any]]) -> bool:
    if not isinstance(actual, list) or len(actual) != len(expected):
        return False
    keys = ("index", "field", "command", "query", "expected_readback")
    return all(
        isinstance(actual_item, dict)
        and all(actual_item.get(key) == expected_item.get(key) for key in keys)
        for actual_item, expected_item in zip(actual, expected)
    )


def _apply_steps_match_expected(steps: Any, expected: list[dict[str, Any]]) -> bool:
    if not isinstance(steps, list) or len(steps) != len(expected):
        return False
    keys = ("index", "field", "command", "query", "expected_readback")
    return all(
        isinstance(step, dict)
        and all(step.get(key) == expected_item.get(key) for key in keys)
        and sr860_readback_matches(
            str(expected_item.get("field")),
            str(expected_item.get("expected_readback")),
            None if step.get("actual_readback") is None else str(step.get("actual_readback")),
        )
        for step, expected_item in zip(steps, expected)
    )
