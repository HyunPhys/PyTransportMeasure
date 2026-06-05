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
class SMUHardwareParameterAudit:
    role: str
    instrument_id: str | None
    address: str | None
    terminal: str | None
    voltage_range_v: float | None
    current_range_a: float | None
    nplc: float | None
    source_delay_s: float | None
    current_compliance_a: float | None
    required_parameters: tuple[str, ...]
    missing_required_parameters: tuple[str, ...]

    @property
    def is_keithley_2450(self) -> bool:
        return self.instrument_id == "keithley_2450"

    @property
    def ok_for_hardware(self) -> bool:
        return not self.is_keithley_2450 or not self.missing_required_parameters


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


def smu_role_current_compliance(recipe: Any, role: str) -> float | None:
    sweep_attribute_by_role = {
        "instrument": "sweep",
        "source": "bias_sweep",
        "drain": "drain_sweep",
        "gate": "gate_sweep",
        "gate1": "gate1_sweep",
        "gate2": "gate2_sweep",
    }
    sweep = getattr(recipe, sweep_attribute_by_role.get(role, ""), None)
    if sweep is not None:
        value = getattr(sweep, "current_compliance_a", None)
        return None if value is None else float(value)
    pulse = getattr(recipe, "pulse", None)
    value = getattr(pulse, "current_compliance_a", None) if role == "source" and pulse is not None else None
    return None if value is None else float(value)


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


def audit_smu_hardware_parameters(
    recipe: Any,
    roles: tuple[str, ...] | None = None,
) -> tuple[SMUHardwareParameterAudit, ...]:
    allowed_roles = set(roles) if roles is not None else None
    audits: list[SMUHardwareParameterAudit] = []
    required = tuple(spec.parameter for spec in REQUIRED_KEITHLEY_HARDWARE_PARAMETERS)
    for role, instrument in smu_instrument_roles(recipe):
        if allowed_roles is not None and role not in allowed_roles:
            continue
        instrument_id = getattr(instrument, "id", None)
        required_parameters = required if instrument_id == "keithley_2450" else ()
        missing = tuple(parameter for parameter in required_parameters if getattr(instrument, parameter, None) is None)
        audits.append(
            SMUHardwareParameterAudit(
                role=role,
                instrument_id=instrument_id,
                address=getattr(instrument, "address", None),
                terminal=getattr(instrument, "terminal", None),
                voltage_range_v=_optional_float(getattr(instrument, "voltage_range_v", None)),
                current_range_a=_optional_float(getattr(instrument, "current_range_a", None)),
                nplc=_optional_float(getattr(instrument, "nplc", None)),
                source_delay_s=_optional_float(getattr(instrument, "source_delay_s", None)),
                current_compliance_a=smu_role_current_compliance(recipe, role),
                required_parameters=required_parameters,
                missing_required_parameters=missing,
            )
        )
    return tuple(audits)


def smu_hardware_parameter_audit_to_dict(
    audits: tuple[SMUHardwareParameterAudit, ...],
) -> dict[str, Any]:
    return {
        "ok_for_hardware": all(audit.ok_for_hardware for audit in audits),
        "roles": [
            {
                "role": audit.role,
                "instrument_id": audit.instrument_id,
                "address": audit.address,
                "terminal": audit.terminal,
                "voltage_range_v": audit.voltage_range_v,
                "current_range_a": audit.current_range_a,
                "nplc": audit.nplc,
                "source_delay_s": audit.source_delay_s,
                "current_compliance_a": audit.current_compliance_a,
                "required_parameters": list(audit.required_parameters),
                "missing_required_parameters": list(audit.missing_required_parameters),
                "ok_for_hardware": audit.ok_for_hardware,
            }
            for audit in audits
        ],
    }


def format_smu_hardware_parameter_audit(audits: tuple[SMUHardwareParameterAudit, ...]) -> str:
    lines = [
        "Keithley SMU hardware parameter audit",
        f"Hardware-ready: {all(audit.ok_for_hardware for audit in audits)}",
        "",
        "| Role | Instrument | Address | Terminal | V range (V) | I range (A) | NPLC | Source delay (s) | Compliance (A) | Status |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    if not audits:
        lines.append("| n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | NO SMU |")
    for audit in audits:
        status = "PASS" if audit.ok_for_hardware else "MISSING " + ", ".join(audit.missing_required_parameters)
        lines.append(
            "| "
            + " | ".join(
                [
                    audit.role,
                    audit.instrument_id or "n/a",
                    f"`{audit.address}`" if audit.address else "n/a",
                    audit.terminal or "unchanged",
                    _fmt_optional(audit.voltage_range_v),
                    _fmt_optional(audit.current_range_a),
                    _fmt_optional(audit.nplc),
                    _fmt_optional(audit.source_delay_s),
                    _fmt_optional(audit.current_compliance_a),
                    status,
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "Required for Keithley 2450 hardware output:",
            *[
                f"- {spec.parameter}: {spec.label}; {spec.reason}."
                for spec in REQUIRED_KEITHLEY_HARDWARE_PARAMETERS
            ],
        ]
    )
    return "\n".join(lines)


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


def _optional_float(value: Any) -> float | None:
    return None if value is None else float(value)


def _fmt_optional(value: float | None) -> str:
    return "auto" if value is None else f"{value:.6g}"
