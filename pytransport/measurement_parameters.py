"""Measurement-parameter guards for hardware runs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class MeasurementParameterIssue:
    role: str
    parameter: str
    message: str


@dataclass(frozen=True)
class KeithleyHardwareParameterSpec:
    parameter: str
    label: str
    reason: str


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


REQUIRED_KEITHLEY_HARDWARE_PARAMETERS = (
    KeithleyHardwareParameterSpec(
        parameter="nplc",
        label="NPLC",
        reason="sets Keithley current integration time in power-line cycles",
    ),
    KeithleyHardwareParameterSpec(
        parameter="voltage_range_v",
        label="voltage range",
        reason="keeps the voltage source range explicit and auditable",
    ),
    KeithleyHardwareParameterSpec(
        parameter="current_range_a",
        label="current range",
        reason="avoids accidental current autorange during hardware scans",
    ),
)


def missing_explicit_nplc(recipe: Any, roles: tuple[str, ...] | None = None) -> tuple[MeasurementParameterIssue, ...]:
    return tuple(
        issue
        for issue in missing_required_smu_hardware_parameters(recipe, roles)
        if issue.parameter == "nplc"
    )


def missing_required_smu_hardware_parameters(
    recipe: Any,
    roles: tuple[str, ...] | None = None,
) -> tuple[MeasurementParameterIssue, ...]:
    allowed_roles = set(roles) if roles is not None else None
    issues: list[MeasurementParameterIssue] = []
    for role, instrument in smu_instrument_roles(recipe):
        if allowed_roles is not None and role not in allowed_roles:
            continue
        if getattr(instrument, "id", None) != "keithley_2450":
            continue
        for spec in REQUIRED_KEITHLEY_HARDWARE_PARAMETERS:
            if getattr(instrument, spec.parameter, None) is None:
                issues.append(
                    MeasurementParameterIssue(
                        role=role,
                        parameter=spec.parameter,
                        message=f"{role} Keithley 2450 hardware runs require explicit {spec.label}; {spec.reason}",
                    )
                )
    return tuple(issues)


def format_measurement_parameter_issues(issues: tuple[MeasurementParameterIssue, ...]) -> str:
    lines = ["Measurement parameter check failed:"]
    for issue in issues:
        lines.append(f"- {issue.role}.{issue.parameter}: {issue.message}")
    lines.append("Set the missing value in the recipe before enabling hardware output.")
    lines.append("Keithley 2450 hardware parameter policy:")
    for spec in REQUIRED_KEITHLEY_HARDWARE_PARAMETERS:
        lines.append(f"- {spec.parameter}: {spec.label}; {spec.reason}.")
    return "\n".join(lines)


def assert_explicit_nplc_for_hardware(recipe: Any, roles: tuple[str, ...] | None = None) -> None:
    issues = missing_explicit_nplc(recipe, roles)
    if issues:
        raise ValueError(format_measurement_parameter_issues(issues))


def assert_required_smu_parameters_for_hardware(recipe: Any, roles: tuple[str, ...] | None = None) -> None:
    issues = missing_required_smu_hardware_parameters(recipe, roles)
    if issues:
        raise ValueError(format_measurement_parameter_issues(issues))
