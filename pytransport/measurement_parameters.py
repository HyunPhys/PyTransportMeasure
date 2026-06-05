"""Measurement-parameter guards for hardware runs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class MeasurementParameterIssue:
    role: str
    parameter: str
    message: str


def smu_instrument_roles(recipe: Any) -> tuple[tuple[str, Any], ...]:
    roles = [
        ("instrument", "instrument"),
        ("source", "source_instrument"),
        ("drain", "drain_instrument"),
        ("gate", "gate_instrument"),
        ("gate1", "gate1_instrument"),
        ("gate2", "gate2_instrument"),
    ]
    found: list[tuple[str, Any]] = []
    for role, attribute in roles:
        instrument = getattr(recipe, attribute, None)
        if instrument is not None:
            found.append((role, instrument))
    return tuple(found)


def missing_explicit_nplc(recipe: Any, roles: tuple[str, ...] | None = None) -> tuple[MeasurementParameterIssue, ...]:
    allowed_roles = set(roles) if roles is not None else None
    issues: list[MeasurementParameterIssue] = []
    for role, instrument in smu_instrument_roles(recipe):
        if allowed_roles is not None and role not in allowed_roles:
            continue
        if getattr(instrument, "id", None) != "keithley_2450":
            continue
        if getattr(instrument, "nplc", None) is None:
            issues.append(
                MeasurementParameterIssue(
                    role=role,
                    parameter="nplc",
                    message=f"{role} Keithley 2450 hardware runs require explicit NPLC",
                )
            )
    return tuple(issues)


def format_measurement_parameter_issues(issues: tuple[MeasurementParameterIssue, ...]) -> str:
    lines = ["Measurement parameter check failed:"]
    for issue in issues:
        lines.append(f"- {issue.role}.{issue.parameter}: {issue.message}")
    lines.append("Set the missing value in the recipe before enabling hardware output.")
    return "\n".join(lines)


def assert_explicit_nplc_for_hardware(recipe: Any, roles: tuple[str, ...] | None = None) -> None:
    issues = missing_explicit_nplc(recipe, roles)
    if issues:
        raise ValueError(format_measurement_parameter_issues(issues))
