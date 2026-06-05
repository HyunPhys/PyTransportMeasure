"""Design gate for future Keithley 2450 four-terminal DC measurements."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .recipes import DrainIVRecipe, load_yaml


@dataclass(frozen=True)
class FourTerminalDCDesignIssue:
    severity: str
    field: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class FourTerminalDCDesignGate:
    ready_for_implementation: bool
    active_hardware_run_allowed: bool
    recipe_path: str | None
    measurement_name: str | None
    measurement_geometry: dict[str, Any] | None
    proposed_recipe_fields: tuple[str, ...]
    required_driver_commands: tuple[str, ...]
    required_readback_queries: tuple[str, ...]
    required_contact_guards: tuple[str, ...]
    implementation_todos: tuple[str, ...]
    issues: tuple[FourTerminalDCDesignIssue, ...]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["issues"] = [issue.to_dict() for issue in self.issues]
        return payload


PROPOSED_RECIPE_FIELDS = (
    "measurement_geometry.method: four_terminal",
    "measurement_geometry.terminal_count: 4",
    "dc_sense_mode: local_2wire | remote_4wire",
    "source_contact",
    "drain_contact",
    "sense_hi_contact",
    "sense_lo_contact",
    "sense_terminal_warning_acknowledged",
)

REQUIRED_DRIVER_COMMANDS = (
    "*LANG? must return SCPI",
    ":SENS:FUNC \"CURR\"",
    ":SENS:CURR:RSEN ON for remote_4wire Drain I-V current measurement",
    ":SENS:CURR:RSEN OFF or documented local equivalent for local_2wire",
    ":SOUR:FUNC VOLT",
    ":SOUR:VOLT:ILIM or :SOUR:VOLT:ILIMIT current compliance",
    ":SOUR:VOLT 0 before :OUTP OFF",
)

REQUIRED_READBACK_QUERIES = (
    ":SENS:FUNC?",
    ":SENS:CURR:RSEN?",
    ":SENS:CURR:NPLC?",
    ":SENS:CURR:RANG?",
    ":SOUR:FUNC?",
    ":SOUR:VOLT:RANG?",
    ":SOUR:VOLT:ILIM? or accepted fallback query",
)

REQUIRED_CONTACT_GUARDS = (
    "source_contact and drain_contact must be distinct",
    "sense_hi_contact and sense_lo_contact must be distinct",
    "remote_4wire requires force and sense contacts to be explicitly named",
    "front and rear terminals must not be mixed",
    "sense leads must be connected before remote sense is enabled",
)

IMPLEMENTATION_TODOS = (
    "Add method-specific recipe schema instead of a generic global remote-sense flag.",
    "Add fake driver metadata support without claiming improved physics.",
    "Add Keithley driver unit tests for exact remote-sense SCPI sequence.",
    "Add preflight readback for :SENS:CURR:RSEN? before enabling output.",
    "Add resistor/contact-fixture hardware smoke recipe only after driver tests pass.",
)


def inspect_four_terminal_dc_design_gate(recipe_path: str | Path | None = None) -> FourTerminalDCDesignGate:
    issues = [
        FourTerminalDCDesignIssue(
            severity="blocker",
            field="runner",
            message="No active four-terminal DC runner is implemented; hardware output remains blocked.",
        ),
        FourTerminalDCDesignIssue(
            severity="blocker",
            field="schema",
            message="Method-specific dc_sense_mode/contact fields are not implemented yet.",
        ),
    ]
    measurement_name = None
    measurement_geometry = None
    if recipe_path is not None:
        recipe_data = load_yaml(Path(recipe_path))
        recipe = DrainIVRecipe.model_validate(recipe_data)
        measurement_name = recipe.measurement_name
        measurement_geometry = recipe.measurement_geometry.model_dump(mode="json")
        if recipe.measurement_geometry.method != "four_terminal":
            issues.append(
                FourTerminalDCDesignIssue(
                    severity="warning",
                    field="measurement_geometry.method",
                    message="Candidate recipe is not a four_terminal Drain I-V recipe.",
                )
            )
        if recipe.measurement_geometry.terminal_count != 4:
            issues.append(
                FourTerminalDCDesignIssue(
                    severity="warning",
                    field="measurement_geometry.terminal_count",
                    message="Candidate recipe does not declare terminal_count=4.",
                )
            )
        missing_parameters = [
            name
            for name in ("voltage_range_v", "current_range_a", "nplc")
            if getattr(recipe.instrument, name) is None
        ]
        for parameter in missing_parameters:
            issues.append(
                FourTerminalDCDesignIssue(
                    severity="warning",
                    field=f"instrument.{parameter}",
                    message=f"Candidate recipe should declare explicit Keithley {parameter} before 4-wire smoke tests.",
                )
            )
    return FourTerminalDCDesignGate(
        ready_for_implementation=False,
        active_hardware_run_allowed=False,
        recipe_path=str(Path(recipe_path)) if recipe_path is not None else None,
        measurement_name=measurement_name,
        measurement_geometry=measurement_geometry,
        proposed_recipe_fields=PROPOSED_RECIPE_FIELDS,
        required_driver_commands=REQUIRED_DRIVER_COMMANDS,
        required_readback_queries=REQUIRED_READBACK_QUERIES,
        required_contact_guards=REQUIRED_CONTACT_GUARDS,
        implementation_todos=IMPLEMENTATION_TODOS,
        issues=tuple(issues),
    )


def format_four_terminal_dc_design_gate(report: FourTerminalDCDesignGate) -> str:
    lines = [
        "Four-terminal DC design gate",
        f"Ready for implementation: {report.ready_for_implementation}",
        f"Active hardware run allowed: {report.active_hardware_run_allowed}",
    ]
    if report.recipe_path:
        lines.extend(
            [
                f"Recipe: {report.recipe_path}",
                f"Measurement name: {report.measurement_name}",
                f"Measurement geometry: {report.measurement_geometry}",
            ]
        )
    lines.extend(
        [
            "",
            "Issues:",
            *[f"- [{issue.severity}] {issue.field}: {issue.message}" for issue in report.issues],
            "",
            "Proposed recipe fields:",
            *[f"- {field}" for field in report.proposed_recipe_fields],
            "",
            "Required Keithley 2450 SCPI commands:",
            *[f"- {command}" for command in report.required_driver_commands],
            "",
            "Required readback queries:",
            *[f"- {query}" for query in report.required_readback_queries],
            "",
            "Required contact guards:",
            *[f"- {guard}" for guard in report.required_contact_guards],
            "",
            "Implementation TODO:",
            *[f"- {todo}" for todo in report.implementation_todos],
        ]
    )
    return "\n".join(lines)


def write_four_terminal_dc_design_gate_json(
    report: FourTerminalDCDesignGate,
    output_path: str | Path,
) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
    return path
