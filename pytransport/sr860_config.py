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


def write_sr860_config_command_review_json(payload: dict[str, Any], output_path: str | Path) -> Path:
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
