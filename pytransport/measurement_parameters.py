"""Measurement-parameter guards for hardware runs."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from .instrument_specs import KEITHLEY_2450_CURRENT_NPLC_MAX, KEITHLEY_2450_CURRENT_NPLC_MIN


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
class LockInHardwareParameterAudit:
    role: str
    instrument_id: str | None
    address: str | None
    reference_source: str | None
    reference_frequency_hz: float | None
    sine_output_amplitude_v: float | None
    input_mode: str | None
    voltage_input: str | None
    input_coupling: str | None
    input_grounding: str | None
    voltage_input_range_v: float | None
    sensitivity_index: int | None
    time_constant_index: int | None
    settle_time_constants: float | None
    read_settle_s: float | None
    filter_slope_db_per_oct: int | None
    synchronous_filter: bool | None
    required_parameters: tuple[str, ...]
    missing_required_parameters: tuple[str, ...]
    settle_policy_ok: bool

    @property
    def is_srs_sr860(self) -> bool:
        return self.instrument_id == "srs_sr860"

    @property
    def ok_for_hardware(self) -> bool:
        return not self.is_srs_sr860 or (not self.missing_required_parameters and self.settle_policy_ok)


@dataclass(frozen=True)
class KeithleyHardwareParameterSpec:
    parameter: str
    label: str
    reason: str
    valid_range: tuple[float, float] | None = None


@dataclass(frozen=True)
class LockInHardwareParameterSpec:
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


def lockin_instrument_roles(recipe: Any) -> tuple[tuple[str, Any], ...]:
    lockin = getattr(recipe, "lockin", None)
    if lockin is None:
        return ()
    return (("lockin", lockin),)


REQUIRED_KEITHLEY_HARDWARE_PARAMETERS = (
    KeithleyHardwareParameterSpec(
        parameter="nplc",
        label="NPLC",
        reason="sets Keithley current integration time in power-line cycles",
        valid_range=(KEITHLEY_2450_CURRENT_NPLC_MIN, KEITHLEY_2450_CURRENT_NPLC_MAX),
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


REQUIRED_SR860_HARDWARE_PARAMETERS = (
    LockInHardwareParameterSpec(
        parameter="reference_source",
        label="reference source",
        reason="fixes whether the SR860 uses internal, external, dual, or chopped reference",
    ),
    LockInHardwareParameterSpec(
        parameter="reference_frequency_hz",
        label="reference frequency",
        reason="sets the excitation/reference frequency used for phase-sensitive detection",
    ),
    LockInHardwareParameterSpec(
        parameter="sine_output_amplitude_v",
        label="sine output amplitude",
        reason="sets the AC excitation amplitude when the SR860 drives the circuit",
    ),
    LockInHardwareParameterSpec(
        parameter="input_mode",
        label="input mode",
        reason="declares whether the SR860 input is voltage or current",
    ),
    LockInHardwareParameterSpec(
        parameter="voltage_input",
        label="voltage input",
        reason="declares A or A-B voltage input wiring",
    ),
    LockInHardwareParameterSpec(
        parameter="input_coupling",
        label="input coupling",
        reason="declares AC/DC input coupling",
    ),
    LockInHardwareParameterSpec(
        parameter="input_grounding",
        label="input grounding",
        reason="declares floating or grounded input reference",
    ),
    LockInHardwareParameterSpec(
        parameter="voltage_input_range_v",
        label="voltage input range",
        reason="keeps the SR860 voltage input range explicit and auditable",
    ),
    LockInHardwareParameterSpec(
        parameter="sensitivity_index",
        label="sensitivity index",
        reason="sets the SR860 full-scale sensitivity condition",
    ),
    LockInHardwareParameterSpec(
        parameter="time_constant_index",
        label="time constant index",
        reason="sets the SR860 low-pass time constant",
    ),
    LockInHardwareParameterSpec(
        parameter="filter_slope_db_per_oct",
        label="filter slope",
        reason="sets the SR860 low-pass roll-off",
    ),
    LockInHardwareParameterSpec(
        parameter="synchronous_filter",
        label="synchronous filter",
        reason="declares the synchronous filter state",
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


def audit_lockin_hardware_parameters(
    recipe: Any,
    roles: tuple[str, ...] | None = None,
) -> tuple[LockInHardwareParameterAudit, ...]:
    allowed_roles = set(roles) if roles is not None else None
    audits: list[LockInHardwareParameterAudit] = []
    required = tuple(spec.parameter for spec in REQUIRED_SR860_HARDWARE_PARAMETERS)
    for role, lockin in lockin_instrument_roles(recipe):
        if allowed_roles is not None and role not in allowed_roles:
            continue
        instrument_id = getattr(lockin, "id", None)
        required_parameters = required if instrument_id == "srs_sr860" else ()
        missing = tuple(parameter for parameter in required_parameters if getattr(lockin, parameter, None) is None)
        settle_time_constants = _optional_float(getattr(lockin, "settle_time_constants", None))
        read_settle_s = _optional_float(getattr(lockin, "read_settle_s", None))
        time_constant_index = _optional_int(getattr(lockin, "time_constant_index", None))
        settle_policy_ok = (
            read_settle_s is not None
            and read_settle_s > 0
        ) or (
            time_constant_index is not None
            and settle_time_constants is not None
            and settle_time_constants > 0
        )
        audits.append(
            LockInHardwareParameterAudit(
                role=role,
                instrument_id=instrument_id,
                address=getattr(lockin, "address", None),
                reference_source=getattr(lockin, "reference_source", None),
                reference_frequency_hz=_optional_float(getattr(lockin, "reference_frequency_hz", None)),
                sine_output_amplitude_v=_optional_float(getattr(lockin, "sine_output_amplitude_v", None)),
                input_mode=getattr(lockin, "input_mode", None),
                voltage_input=getattr(lockin, "voltage_input", None),
                input_coupling=getattr(lockin, "input_coupling", None),
                input_grounding=getattr(lockin, "input_grounding", None),
                voltage_input_range_v=_optional_float(getattr(lockin, "voltage_input_range_v", None)),
                sensitivity_index=_optional_int(getattr(lockin, "sensitivity_index", None)),
                time_constant_index=time_constant_index,
                settle_time_constants=settle_time_constants,
                read_settle_s=read_settle_s,
                filter_slope_db_per_oct=_optional_int(getattr(lockin, "filter_slope_db_per_oct", None)),
                synchronous_filter=getattr(lockin, "synchronous_filter", None),
                required_parameters=required_parameters,
                missing_required_parameters=missing,
                settle_policy_ok=settle_policy_ok,
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


def lockin_hardware_parameter_audit_to_dict(
    audits: tuple[LockInHardwareParameterAudit, ...],
) -> dict[str, Any]:
    return {
        "ok_for_hardware": all(audit.ok_for_hardware for audit in audits),
        "roles": [
            {
                "role": audit.role,
                "instrument_id": audit.instrument_id,
                "address": audit.address,
                "reference_source": audit.reference_source,
                "reference_frequency_hz": audit.reference_frequency_hz,
                "sine_output_amplitude_v": audit.sine_output_amplitude_v,
                "input_mode": audit.input_mode,
                "voltage_input": audit.voltage_input,
                "input_coupling": audit.input_coupling,
                "input_grounding": audit.input_grounding,
                "voltage_input_range_v": audit.voltage_input_range_v,
                "sensitivity_index": audit.sensitivity_index,
                "time_constant_index": audit.time_constant_index,
                "settle_time_constants": audit.settle_time_constants,
                "read_settle_s": audit.read_settle_s,
                "filter_slope_db_per_oct": audit.filter_slope_db_per_oct,
                "synchronous_filter": audit.synchronous_filter,
                "required_parameters": list(audit.required_parameters),
                "missing_required_parameters": list(audit.missing_required_parameters),
                "settle_policy_ok": audit.settle_policy_ok,
                "ok_for_hardware": audit.ok_for_hardware,
            }
            for audit in audits
        ],
    }


def measurement_parameter_audit_to_dict(recipe: Any) -> dict[str, Any]:
    smu_audits = audit_smu_hardware_parameters(recipe)
    lockin_audits = audit_lockin_hardware_parameters(recipe)
    smu_payload = smu_hardware_parameter_audit_to_dict(smu_audits)
    lockin_payload = lockin_hardware_parameter_audit_to_dict(lockin_audits)
    return {
        "ok_for_hardware": smu_payload["ok_for_hardware"] and lockin_payload["ok_for_hardware"],
        "smu": smu_payload,
        "lockin": lockin_payload,
    }


def build_measurement_parameter_audit_payload(
    measurement_type: str,
    recipe_path: str | Path,
    recipe: Any,
) -> dict[str, Any]:
    return {
        "schema": "pytransport.measurement_parameter_audit.v1",
        "measurement_type": measurement_type,
        "recipe": str(recipe_path),
        **measurement_parameter_audit_to_dict(recipe),
    }


def load_measurement_parameter_audit_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def check_measurement_parameter_audit_evidence(
    measurement_type: str,
    recipe_path: str | Path,
    recipe: Any,
    saved_payload: dict[str, Any],
) -> dict[str, Any]:
    current_payload = build_measurement_parameter_audit_payload(measurement_type, recipe_path, recipe)
    checks = [
        _evidence_check(
            "schema",
            saved_payload.get("schema") in {None, current_payload["schema"]},
            f"expected {current_payload['schema']}",
            saved_payload.get("schema"),
        ),
        _evidence_check(
            "measurement_type",
            saved_payload.get("measurement_type") == current_payload["measurement_type"],
            current_payload["measurement_type"],
            saved_payload.get("measurement_type"),
        ),
        _evidence_check(
            "recipe",
            _same_recipe_path(saved_payload.get("recipe"), current_payload["recipe"]),
            current_payload["recipe"],
            saved_payload.get("recipe"),
        ),
        _evidence_check(
            "ok_for_hardware",
            saved_payload.get("ok_for_hardware") == current_payload["ok_for_hardware"],
            current_payload["ok_for_hardware"],
            saved_payload.get("ok_for_hardware"),
        ),
        _evidence_check(
            "smu_parameters",
            saved_payload.get("smu") == current_payload["smu"],
            current_payload["smu"],
            saved_payload.get("smu"),
        ),
        _evidence_check(
            "lockin_parameters",
            saved_payload.get("lockin") == current_payload["lockin"],
            current_payload["lockin"],
            saved_payload.get("lockin"),
        ),
    ]
    return {
        "schema": "pytransport.measurement_parameter_audit_evidence.v1",
        "ok": all(check["ok"] for check in checks),
        "measurement_type": measurement_type,
        "recipe": str(recipe_path),
        "checks": checks,
        "current_audit": current_payload,
        "saved_audit": saved_payload,
    }


def check_measurement_parameter_audit_evidence_file(
    measurement_type: str,
    recipe_path: str | Path,
    recipe: Any,
    audit_json: str | Path,
) -> dict[str, Any]:
    payload = check_measurement_parameter_audit_evidence(
        measurement_type,
        recipe_path,
        recipe,
        load_measurement_parameter_audit_json(audit_json),
    )
    return {"audit_json": str(audit_json), **payload}


def format_measurement_parameter_audit_evidence_check(payload: dict[str, Any]) -> str:
    lines = [
        "Measurement parameter audit evidence check",
        f"Audit JSON: {payload.get('audit_json', 'n/a')}",
        f"Measurement type: {payload['measurement_type']}",
        f"Recipe: {payload['recipe']}",
        f"OK: {payload['ok']}",
        "",
        "| Check | OK | Expected/current | Saved |",
        "| --- | --- | --- | --- |",
    ]
    for check in payload["checks"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    check["key"],
                    str(check["ok"]),
                    _fmt_evidence_value(check["expected"]),
                    _fmt_evidence_value(check["actual"]),
                ]
            )
            + " |"
        )
    return "\n".join(lines)


def write_measurement_parameter_audit_evidence_check_json(payload: dict[str, Any], output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


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
                f"- {spec.parameter}: {spec.label}; {spec.reason}{_format_valid_range(spec)}."
                for spec in REQUIRED_KEITHLEY_HARDWARE_PARAMETERS
            ],
        ]
    )
    return "\n".join(lines)


def format_lockin_hardware_parameter_audit(audits: tuple[LockInHardwareParameterAudit, ...]) -> str:
    lines = [
        "SR860 lock-in hardware parameter audit",
        f"Hardware-ready: {all(audit.ok_for_hardware for audit in audits)}",
        "",
        "| Role | Instrument | Address | Ref | Freq (Hz) | Sine (V) | Input | Vin | Range (V) | Sens idx | TC idx | Settle TC | Read settle (s) | Slope | Sync | Status |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    if not audits:
        lines.append("| n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | NO LOCK-IN |")
    for audit in audits:
        status_items: list[str] = []
        if audit.missing_required_parameters:
            status_items.append("MISSING " + ", ".join(audit.missing_required_parameters))
        if audit.is_srs_sr860 and not audit.settle_policy_ok:
            status_items.append("MISSING positive settle policy")
        status = "PASS" if not status_items else "; ".join(status_items)
        lines.append(
            "| "
            + " | ".join(
                [
                    audit.role,
                    audit.instrument_id or "n/a",
                    f"`{audit.address}`" if audit.address else "n/a",
                    audit.reference_source or "auto",
                    _fmt_optional(audit.reference_frequency_hz),
                    _fmt_optional(audit.sine_output_amplitude_v),
                    audit.input_mode or "auto",
                    audit.voltage_input or "auto",
                    _fmt_optional(audit.voltage_input_range_v),
                    _fmt_optional_int(audit.sensitivity_index),
                    _fmt_optional_int(audit.time_constant_index),
                    _fmt_optional(audit.settle_time_constants),
                    _fmt_optional(audit.read_settle_s),
                    _fmt_optional_int(audit.filter_slope_db_per_oct),
                    "auto" if audit.synchronous_filter is None else str(audit.synchronous_filter),
                    status,
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "Required for SR860 hardware output:",
            *[
                f"- {spec.parameter}: {spec.label}; {spec.reason}."
                for spec in REQUIRED_SR860_HARDWARE_PARAMETERS
            ],
            "- settle policy: set read_settle_s > 0, or set time_constant_index with settle_time_constants > 0.",
        ]
    )
    return "\n".join(lines)


def format_measurement_parameter_audit(recipe: Any) -> str:
    payload = measurement_parameter_audit_to_dict(recipe)
    return "\n\n".join(
        [
            "Measurement parameter audit",
            f"Hardware-ready: {payload['ok_for_hardware']}",
            format_smu_hardware_parameter_audit(audit_smu_hardware_parameters(recipe)),
            format_lockin_hardware_parameter_audit(audit_lockin_hardware_parameters(recipe)),
        ]
    )


def _evidence_check(key: str, ok: bool, expected: Any, actual: Any) -> dict[str, Any]:
    return {
        "key": key,
        "ok": bool(ok),
        "expected": expected,
        "actual": actual,
    }


def _same_recipe_path(saved: Any, current: str) -> bool:
    if saved is None:
        return False
    try:
        return Path(str(saved)).resolve() == Path(current).resolve()
    except OSError:
        return str(saved).replace("\\", "/") == str(current).replace("\\", "/")


def _fmt_evidence_value(value: Any) -> str:
    if isinstance(value, (dict, list)):
        text = json.dumps(value, sort_keys=True)
    else:
        text = str(value)
    text = text.replace("|", "\\|")
    if len(text) > 120:
        return text[:117] + "..."
    return text


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
                        message=(
                            f"{role} Keithley 2450 hardware runs require explicit {spec.label}; "
                            f"{spec.reason}{_format_valid_range(spec)}"
                        ),
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
        lines.append(f"- {spec.parameter}: {spec.label}; {spec.reason}{_format_valid_range(spec)}.")
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


def _optional_int(value: Any) -> int | None:
    return None if value is None else int(value)


def _fmt_optional(value: float | None) -> str:
    return "auto" if value is None else f"{value:.6g}"


def _fmt_optional_int(value: int | None) -> str:
    return "auto" if value is None else str(value)


def _format_valid_range(spec: KeithleyHardwareParameterSpec) -> str:
    if spec.valid_range is None:
        return ""
    low, high = spec.valid_range
    return f"; valid recipe range {low:g} to {high:g}"
