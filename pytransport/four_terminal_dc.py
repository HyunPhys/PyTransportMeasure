"""Design gate for future Keithley 2450 four-terminal DC measurements."""

from __future__ import annotations

import json
import random
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from pydantic import ValidationError

from .errors import SafetyLimitError
from .instruments.fake import fake_voltage_source_config_readback
from .io import RunWriter
from .model import MeasurementPoint
from .output_state import (
    command_voltage_with_state,
    initialize_output_state,
    output_off_with_state,
    output_on_with_state,
    zero_before_off_with_state,
)
from .recipes import DrainIVRecipe, FourTerminalDCRecipe, SafetyPreset, load_four_terminal_dc_recipe, load_yaml, sweep_delays, sweep_voltages
from .safety import validate_point_current
from .smu_config import (
    build_voltage_source_config,
    compare_voltage_source_config_readback,
    raise_for_voltage_source_config_readback_mismatch,
    read_voltage_source_config_if_available,
    voltage_source_config_snapshot,
)


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


@dataclass(frozen=True)
class FourTerminalDCPreflightCheck:
    name: str
    ok: bool
    expected: str | None = None
    actual: str | None = None
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FourTerminalDCPreflightReport:
    recipe_path: str
    measurement_name: str
    address: str
    dry_check: bool
    hardware_checked: bool
    hardware_connected: bool
    active_hardware_run_allowed: bool
    preflight_passed: bool
    idn: str | None
    language: str | None
    system_error: str | None
    remote_sense_readback: str | None
    readback_snapshot: dict[str, str | None]
    error_type: str | None
    error_message: str | None
    checks: tuple[FourTerminalDCPreflightCheck, ...]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["checks"] = [check.to_dict() for check in self.checks]
        return payload


@dataclass(frozen=True)
class FourTerminalDCCommandStep:
    order: int
    phase: str
    command: str
    purpose: str
    required_readback: str | None = None
    blocks_output_until_pass: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FourTerminalDCCommandReview:
    recipe_path: str
    measurement_name: str
    active_hardware_run_allowed: bool
    active_runner_ready: bool
    evidence_passed: bool
    required_preflight_json: str | None
    required_dry_run_metadata: str | None
    command_steps: tuple[FourTerminalDCCommandStep, ...]
    approval_gates: tuple[str, ...]
    evidence_checks: tuple[FourTerminalDCPreflightCheck, ...]
    issues: tuple[FourTerminalDCDesignIssue, ...]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["command_steps"] = [step.to_dict() for step in self.command_steps]
        payload["evidence_checks"] = [check.to_dict() for check in self.evidence_checks]
        payload["issues"] = [issue.to_dict() for issue in self.issues]
        return payload


PROPOSED_RECIPE_FIELDS = (
    "measurement_geometry.method: four_terminal",
    "measurement_geometry.terminal_count: 4",
    "dc_sense_mode: remote_4wire",
    "contacts.source_contact",
    "contacts.drain_contact",
    "contacts.sense_hi_contact",
    "contacts.sense_lo_contact",
    "contacts.terminal_plane",
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
    "Keep the FourTerminalDCRecipe schema non-executable until preflight and runner phases pass.",
    "Add fake driver metadata support without claiming improved physics.",
    "Require a passing four-terminal-dc-preflight report before adding an active runner.",
    "Add resistor/contact-fixture hardware smoke recipe only after preflight and runner tests pass.",
)


def inspect_four_terminal_dc_design_gate(recipe_path: str | Path | None = None) -> FourTerminalDCDesignGate:
    issues = [
        FourTerminalDCDesignIssue(
            severity="blocker",
            field="runner",
            message="No active four-terminal DC runner is implemented; hardware output remains blocked.",
        ),
        FourTerminalDCDesignIssue(
            severity="info",
            field="driver",
            message="Keithley 2450 current remote-sense primitive exists but is not wired into active runners.",
        ),
        FourTerminalDCDesignIssue(
            severity="info",
            field="preflight",
            message="four-terminal-dc-preflight checks recipe parameters and :SENS:CURR:RSEN? without enabling output.",
        ),
    ]
    measurement_name = None
    measurement_geometry = None
    if recipe_path is not None:
        recipe_data = load_yaml(Path(recipe_path))
        try:
            recipe = FourTerminalDCRecipe.model_validate(recipe_data)
            measurement_name = recipe.measurement_name
            measurement_geometry = recipe.measurement_geometry.model_dump(mode="json")
        except ValidationError:
            recipe = DrainIVRecipe.model_validate(recipe_data)
            measurement_name = recipe.measurement_name
            measurement_geometry = recipe.measurement_geometry.model_dump(mode="json")
            issues.append(
                FourTerminalDCDesignIssue(
                    severity="warning",
                    field="schema",
                    message="Candidate recipe still uses DrainIVRecipe shape, not FourTerminalDCRecipe schema draft.",
                )
            )
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


def validate_four_terminal_dc_recipe_file(recipe_path: str | Path) -> FourTerminalDCRecipe:
    return load_four_terminal_dc_recipe(recipe_path)


def format_four_terminal_dc_recipe_validation(recipe: FourTerminalDCRecipe, recipe_path: str | Path) -> str:
    return "\n".join(
        [
            "Four-terminal DC recipe validation: PASS",
            f"Recipe: {Path(recipe_path)}",
            f"Measurement name: {recipe.measurement_name}",
            f"Implementation status: {recipe.implementation_status}",
            f"Sense mode: {recipe.dc_sense_mode}",
            f"Measurement geometry: {recipe.measurement_geometry.method}, {recipe.measurement_geometry.terminal_count}-terminal",
            f"Keithley address: {recipe.instrument.address}",
            f"Keithley terminal: {recipe.instrument.terminal or 'not set'}",
            f"Terminal plane: {recipe.contacts.terminal_plane}",
            f"Voltage range: {recipe.instrument.voltage_range_v} V",
            f"Current range: {recipe.instrument.current_range_a} A",
            f"NPLC: {recipe.instrument.nplc}",
            f"Contacts: force {recipe.contacts.source_contact}->{recipe.contacts.drain_contact}, sense {recipe.contacts.sense_hi_contact}->{recipe.contacts.sense_lo_contact}",
            "Active hardware run allowed: False",
        ]
    )


def run_four_terminal_dc_preflight(
    recipe_path: str | Path,
    *,
    address: str | None = None,
    timeout_ms: int | None = None,
    dry_check: bool = False,
    instrument_factory: Callable[[str, int], Any] | None = None,
) -> FourTerminalDCPreflightReport:
    recipe_path = Path(recipe_path)
    recipe = load_four_terminal_dc_recipe(recipe_path)
    instrument_address = address or recipe.instrument.address
    instrument_timeout_ms = timeout_ms or recipe.instrument.timeout_ms
    checks = _recipe_preflight_checks(recipe)
    idn: str | None = None
    language: str | None = None
    system_error: str | None = None
    remote_sense_readback: str | None = None
    readback_snapshot: dict[str, str | None] = {}
    hardware_checked = False
    hardware_connected = False
    error_type: str | None = None
    error_message: str | None = None

    if dry_check:
        checks.append(
            FourTerminalDCPreflightCheck(
                name="hardware_readback_skipped",
                ok=True,
                expected="dry_check=False for lab readback",
                actual="dry_check=True",
                message="Recipe/preflight structure checked without connecting to hardware.",
            )
        )
    else:
        hardware_checked = True
        try:
            if instrument_factory is None:
                from .instruments.keithley_2450 import Keithley2450

                instrument_factory = Keithley2450
            smu = instrument_factory(instrument_address, instrument_timeout_ms)
            try:
                smu.connect()
                hardware_connected = True
                probe = smu.probe()
                idn = _string_or_none(probe.get("idn"))
                language = _string_or_none(probe.get("language"))
                system_error = _string_or_none(probe.get("system_error"))
                remote_sense_readback = _string_or_none(smu.read_current_remote_sense())
                if hasattr(smu, "read_voltage_source_config"):
                    readback_snapshot = {
                        key: _string_or_none(value)
                        for key, value in smu.read_voltage_source_config().items()
                    }
                checks.extend(
                    _hardware_preflight_checks(
                        language=language,
                        system_error=system_error,
                        remote_sense_readback=remote_sense_readback,
                        readback_snapshot=readback_snapshot,
                    )
                )
            finally:
                smu.close()
        except Exception as exc:
            error_type = type(exc).__name__
            error_message = str(exc)
            checks.append(
                FourTerminalDCPreflightCheck(
                    name="hardware_connection_and_readback",
                    ok=False,
                    expected="connect, probe, and remote-sense readback without enabling output",
                    actual=f"{error_type}: {error_message}",
                    message="Hardware preflight failed before any four-terminal DC runner was allowed.",
                )
            )

    preflight_passed = all(check.ok for check in checks)
    return FourTerminalDCPreflightReport(
        recipe_path=str(recipe_path),
        measurement_name=recipe.measurement_name,
        address=instrument_address,
        dry_check=dry_check,
        hardware_checked=hardware_checked,
        hardware_connected=hardware_connected,
        active_hardware_run_allowed=False,
        preflight_passed=preflight_passed,
        idn=idn,
        language=language,
        system_error=system_error,
        remote_sense_readback=remote_sense_readback,
        readback_snapshot=readback_snapshot,
        error_type=error_type,
        error_message=error_message,
        checks=tuple(checks),
    )


def format_four_terminal_dc_preflight(report: FourTerminalDCPreflightReport) -> str:
    lines = [
        "Four-terminal DC preflight",
        f"Recipe: {report.recipe_path}",
        f"Measurement name: {report.measurement_name}",
        f"Keithley address: {report.address}",
        f"Dry check: {report.dry_check}",
        f"Hardware checked: {report.hardware_checked}",
        f"Hardware connected: {report.hardware_connected}",
        f"Preflight passed: {report.preflight_passed}",
        f"Active hardware run allowed: {report.active_hardware_run_allowed}",
    ]
    if report.idn is not None:
        lines.append(f"IDN: {report.idn}")
    if report.language is not None:
        lines.append(f"Command set: {report.language}")
    if report.system_error is not None:
        lines.append(f"System error: {report.system_error}")
    if report.remote_sense_readback is not None:
        lines.append(f"Remote sense readback (:SENS:CURR:RSEN?): {report.remote_sense_readback}")
    if report.error_message:
        lines.append(f"Error: {report.error_type}: {report.error_message}")
    if report.readback_snapshot:
        lines.extend(["", "Readback snapshot:"])
        for key, value in report.readback_snapshot.items():
            lines.append(f"- {key}: {value}")
    lines.extend(["", "Checks:"])
    for check in report.checks:
        status = "PASS" if check.ok else "FAIL"
        detail = f" expected={check.expected}, actual={check.actual}" if check.expected or check.actual else ""
        suffix = f" - {check.message}" if check.message else ""
        lines.append(f"- [{status}] {check.name}:{detail}{suffix}")
    return "\n".join(lines)


def write_four_terminal_dc_preflight_json(
    report: FourTerminalDCPreflightReport,
    output_path: str | Path,
) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
    return path


def run_four_terminal_dc_dry_run(
    recipe: FourTerminalDCRecipe,
    safety: SafetyPreset,
    *,
    recipe_path: str | Path | None = None,
    fake_resistance_ohm: float = 1_000_000.0,
    fake_noise_std_a: float = 0.0,
    progress_callback: Callable[[MeasurementPoint, int], None] | None = None,
) -> dict[str, Any]:
    if fake_resistance_ohm <= 0:
        raise ValueError("fake_resistance_ohm must be > 0")
    if fake_noise_std_a < 0:
        raise ValueError("fake_noise_std_a must be >= 0")
    _validate_four_terminal_dc_against_safety(recipe, safety)
    writer = RunWriter(Path(recipe.output.directory), recipe.measurement_name)
    writer.write_yaml_snapshot(writer.recipe_snapshot_path, recipe.model_dump(mode="json"))
    writer.write_yaml_snapshot(writer.safety_snapshot_path, safety.model_dump(mode="json"))
    smu_config = build_voltage_source_config(recipe.instrument, recipe.sweep.current_compliance_a)
    metadata: dict[str, Any] = {
        "measurement_name": recipe.measurement_name,
        "measurement_type": "four_terminal_dc",
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "completed": False,
        "interrupted": False,
        "dry_run": True,
        "active_hardware_run_allowed": False,
        "runner_status": "dry_run_skeleton_non_executable_hardware",
        "error_type": None,
        "error_message": None,
        "triggered_limit": None,
        "points_written": 0,
        "recipe": recipe.model_dump(mode="json"),
        "recipe_path": str(Path(recipe_path)) if recipe_path is not None else None,
        "safety": safety.model_dump(mode="json"),
        "run_dir": str(writer.run_dir),
        "csv_path": str(writer.csv_path),
        "metadata_path": str(writer.metadata_path),
        "recipe_snapshot_path": str(writer.recipe_snapshot_path),
        "safety_snapshot_path": str(writer.safety_snapshot_path),
        "plot_path": None,
        "report_path": None,
        "contact_map": recipe.contacts.model_dump(mode="json"),
        "dc_sense_mode": recipe.dc_sense_mode,
        "remote_sense": {
            "scpi_enable_command": ":SENS:CURR:RSEN ON",
            "scpi_readback_query": ":SENS:CURR:RSEN?",
            "configured_in_dry_run": False,
            "active_hardware_output_enabled": False,
        },
        "configured_smu": voltage_source_config_snapshot(smu_config),
        "configured_smu_readback": fake_voltage_source_config_readback(smu_config),
        "fake_model": {
            "kind": "four_terminal_dc_ohmic_current",
            "resistance_ohm": fake_resistance_ohm,
            "noise_std_a": fake_noise_std_a,
            "sense_voltage_v_equals_force_voltage_v": True,
        },
    }
    points_written = 0
    try:
        start = time.monotonic()
        voltages = sweep_voltages(recipe.sweep)
        delays = sweep_delays(recipe.sweep)
        for index, (voltage_v, delay_s) in enumerate(zip(voltages, delays)):
            if delay_s > 0:
                time.sleep(min(delay_s, 0.001))
            current_a = float(voltage_v) / fake_resistance_ohm + random.gauss(0.0, fake_noise_std_a)
            compliance_hit = abs(current_a) >= recipe.sweep.current_compliance_a
            if compliance_hit:
                raise SafetyLimitError("Simulated four-terminal DC compliance was reached", "instrument_compliance")
            validate_point_current(current_a, safety)
            resistance_ohm = None if current_a == 0 else float(voltage_v) / current_a
            point = MeasurementPoint(
                index=index,
                voltage_v=float(voltage_v),
                current_a=current_a,
                elapsed_s=time.monotonic() - start,
                resistance_ohm=resistance_ohm,
                compliance_hit=False,
            )
            writer.write_point(point)
            points_written += 1
            if progress_callback is not None:
                progress_callback(point, len(voltages))
        metadata["completed"] = True
        return metadata
    except SafetyLimitError as exc:
        metadata["error_type"] = type(exc).__name__
        metadata["error_message"] = str(exc)
        metadata["triggered_limit"] = exc.triggered_limit
        return metadata
    except Exception as exc:
        metadata["error_type"] = type(exc).__name__
        metadata["error_message"] = str(exc)
        return metadata
    finally:
        metadata["finished_at"] = datetime.now().isoformat(timespec="seconds")
        metadata["points_written"] = points_written
        writer.write_metadata(metadata)
        writer.close()


def format_four_terminal_dc_dry_run_result(metadata: dict[str, Any]) -> str:
    return "\n".join(
        [
            "Four-terminal DC dry-run",
            f"Run directory: {metadata['run_dir']}",
            f"CSV: {metadata['csv_path']}",
            f"Metadata: {metadata['metadata_path']}",
            f"Completed: {metadata['completed']}",
            f"Points written: {metadata['points_written']}",
            f"Active hardware run allowed: {metadata['active_hardware_run_allowed']}",
            f"NPLC: {metadata['configured_smu'].get('nplc')}",
            f"Voltage range: {metadata['configured_smu'].get('voltage_range_v')} V",
            f"Current range: {metadata['configured_smu'].get('current_range_a')} A",
            f"Compliance: {metadata['configured_smu'].get('current_compliance_a')} A",
            f"Remote sense configured in dry-run: {metadata['remote_sense']['configured_in_dry_run']}",
        ]
    )


def run_four_terminal_dc_active(
    recipe: FourTerminalDCRecipe,
    safety: SafetyPreset,
    smu: Any,
    *,
    recipe_path: str | Path | None = None,
    command_review_json: str | Path,
    hardware_approval_note: str,
    progress_callback: Callable[[MeasurementPoint, int], None] | None = None,
) -> dict[str, Any]:
    approval_note = hardware_approval_note.strip()
    if not approval_note:
        raise ValueError("hardware_approval_note is required for four-terminal DC active runs")
    command_review = validate_four_terminal_dc_command_review_for_active_run(command_review_json)
    _validate_four_terminal_dc_against_safety(recipe, safety)
    writer = RunWriter(Path(recipe.output.directory), recipe.measurement_name)
    writer.write_yaml_snapshot(writer.recipe_snapshot_path, recipe.model_dump(mode="json"))
    writer.write_yaml_snapshot(writer.safety_snapshot_path, safety.model_dump(mode="json"))
    smu_config = build_voltage_source_config(recipe.instrument, recipe.sweep.current_compliance_a)
    metadata: dict[str, Any] = {
        "measurement_name": recipe.measurement_name,
        "measurement_type": "four_terminal_dc",
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "completed": False,
        "interrupted": False,
        "dry_run": False,
        "active_hardware_run_allowed": True,
        "runner_status": "guarded_active_runner_draft",
        "error_type": None,
        "error_message": None,
        "triggered_limit": None,
        "points_written": 0,
        "recipe": recipe.model_dump(mode="json"),
        "recipe_path": str(Path(recipe_path)) if recipe_path is not None else None,
        "safety": safety.model_dump(mode="json"),
        "run_dir": str(writer.run_dir),
        "csv_path": str(writer.csv_path),
        "metadata_path": str(writer.metadata_path),
        "recipe_snapshot_path": str(writer.recipe_snapshot_path),
        "safety_snapshot_path": str(writer.safety_snapshot_path),
        "plot_path": None,
        "report_path": None,
        "contact_map": recipe.contacts.model_dump(mode="json"),
        "dc_sense_mode": recipe.dc_sense_mode,
        "instrument_idn": None,
        "instrument_probe": None,
        "configured_smu": voltage_source_config_snapshot(smu_config),
        "configured_smu_readback": None,
        "configured_smu_readback_check": None,
        "current_limit_command": None,
        "remote_sense": {
            "scpi_enable_command": ":SENS:CURR:RSEN ON",
            "scpi_disable_command": ":SENS:CURR:RSEN OFF",
            "scpi_readback_query": ":SENS:CURR:RSEN?",
            "configured": False,
            "enabled_readback": None,
            "enabled_readback_ok": False,
            "disabled_after_run_attempted": False,
            "disabled_after_run_readback": None,
            "disabled_after_run_error": None,
        },
        "hardware_guard": {
            "command_review_json": str(Path(command_review_json)),
            "command_review_evidence_passed": command_review["evidence_passed"],
            "hardware_approval_note": approval_note,
            "approval_gate": "four_terminal_dc_guarded_active_runner_draft",
        },
    }
    initialize_output_state(metadata, ["instrument"])
    points_written = 0
    try:
        smu.connect()
        probe = smu.probe()
        metadata["instrument_probe"] = probe
        metadata["instrument_idn"] = probe.get("idn")
        smu.configure_voltage_source(smu_config)
        metadata["current_limit_command"] = getattr(smu, "current_limit_command", None)
        metadata["configured_smu_readback"] = read_voltage_source_config_if_available(smu)
        metadata["configured_smu_readback_check"] = compare_voltage_source_config_readback(
            smu_config,
            metadata["configured_smu_readback"],
        )
        raise_for_voltage_source_config_readback_mismatch("instrument", metadata["configured_smu_readback_check"])
        _configure_remote_sense_checked(smu, metadata)
        output_on_with_state("instrument", smu, metadata)
        start = time.monotonic()
        voltages = sweep_voltages(recipe.sweep)
        delays = sweep_delays(recipe.sweep)
        for index, (voltage_v, delay_s) in enumerate(zip(voltages, delays)):
            command_voltage_with_state("instrument", smu, metadata, float(voltage_v))
            if delay_s > 0:
                time.sleep(float(delay_s))
            current_a, compliance_hit = smu.measure_current()
            if compliance_hit:
                raise SafetyLimitError("Instrument compliance was reached", "instrument_compliance")
            validate_point_current(current_a, safety)
            resistance_ohm = None if current_a == 0 else float(voltage_v) / current_a
            point = MeasurementPoint(
                index=index,
                voltage_v=float(voltage_v),
                current_a=float(current_a),
                elapsed_s=time.monotonic() - start,
                resistance_ohm=resistance_ohm,
                compliance_hit=compliance_hit,
            )
            writer.write_point(point)
            points_written += 1
            if progress_callback is not None:
                progress_callback(point, len(voltages))
        metadata["completed"] = True
        return metadata
    except SafetyLimitError as exc:
        metadata["error_type"] = type(exc).__name__
        metadata["error_message"] = str(exc)
        metadata["triggered_limit"] = exc.triggered_limit
        return metadata
    except KeyboardInterrupt as exc:
        metadata["interrupted"] = True
        metadata["error_type"] = type(exc).__name__
        metadata["error_message"] = "Measurement interrupted by user"
        return metadata
    except Exception as exc:
        metadata["error_type"] = type(exc).__name__
        metadata["error_message"] = str(exc)
        return metadata
    finally:
        zero_before_off_with_state("instrument", smu, metadata)
        output_off_with_state("instrument", smu, metadata)
        _disable_remote_sense_after_output_off(smu, metadata)
        smu.close()
        metadata["finished_at"] = datetime.now().isoformat(timespec="seconds")
        metadata["points_written"] = points_written
        writer.write_metadata(metadata)
        writer.close()


def validate_four_terminal_dc_command_review_for_active_run(command_review_json: str | Path) -> dict[str, Any]:
    payload = _load_json_object(Path(command_review_json))
    if payload.get("evidence_passed") is not True:
        raise ValueError("four-terminal DC active run requires command-review evidence_passed=true")
    if payload.get("active_hardware_run_allowed") is not False:
        raise ValueError("command-review JSON must be non-authorizing; expected active_hardware_run_allowed=false")
    commands = [step.get("command") for step in payload.get("command_steps", []) if isinstance(step, dict)]
    _require_command_order(commands, ":SENS:CURR:RSEN ON", ":OUTP ON")
    _require_command_order(commands, ":OUTP ON", ":OUTP OFF")
    if ":SENS:CURR:RSEN OFF" not in commands:
        raise ValueError("command-review JSON must include :SENS:CURR:RSEN OFF cleanup")
    return payload


def review_four_terminal_dc_active_run_commands(
    recipe_path: str | Path,
    *,
    preflight_json: str | Path | None = None,
    dry_run_metadata: str | Path | None = None,
) -> FourTerminalDCCommandReview:
    recipe_path = Path(recipe_path)
    recipe = load_four_terminal_dc_recipe(recipe_path)
    evidence_checks = _active_command_evidence_checks(
        recipe,
        preflight_json=preflight_json,
        dry_run_metadata=dry_run_metadata,
    )
    issues = [
        FourTerminalDCDesignIssue(
            severity="blocker",
            field="active_runner",
            message="Active four-terminal DC hardware runner is still disabled; this command review is not an output path.",
        )
    ]
    if preflight_json is None:
        issues.append(
            FourTerminalDCDesignIssue(
                severity="warning",
                field="preflight_json",
                message="Attach a passing hardware four-terminal-dc-preflight JSON before implementing active output.",
            )
        )
    if dry_run_metadata is None:
        issues.append(
            FourTerminalDCDesignIssue(
                severity="warning",
                field="dry_run_metadata",
                message="Attach completed four-terminal-dc dry-run metadata before implementing active output.",
            )
        )
    return FourTerminalDCCommandReview(
        recipe_path=str(recipe_path),
        measurement_name=recipe.measurement_name,
        active_hardware_run_allowed=False,
        active_runner_ready=False,
        evidence_passed=all(check.ok for check in evidence_checks),
        required_preflight_json=None if preflight_json is None else str(Path(preflight_json)),
        required_dry_run_metadata=None if dry_run_metadata is None else str(Path(dry_run_metadata)),
        command_steps=_four_terminal_dc_active_command_steps(recipe),
        approval_gates=FOUR_TERMINAL_DC_ACTIVE_APPROVAL_GATES,
        evidence_checks=tuple(evidence_checks),
        issues=tuple(issues),
    )


def format_four_terminal_dc_command_review(report: FourTerminalDCCommandReview) -> str:
    lines = [
        "Four-terminal DC active-run command review",
        f"Recipe: {report.recipe_path}",
        f"Measurement name: {report.measurement_name}",
        f"Evidence passed: {report.evidence_passed}",
        f"Active runner ready: {report.active_runner_ready}",
        f"Active hardware run allowed: {report.active_hardware_run_allowed}",
        "",
        "Approval gates:",
        *[f"- {gate}" for gate in report.approval_gates],
        "",
        "| # | Phase | Command | Required readback | Blocks output |",
        "| --- | --- | --- | --- | --- |",
    ]
    for step in report.command_steps:
        lines.append(
            f"| {step.order} | {step.phase} | `{step.command}` | "
            f"{step.required_readback or ''} | {step.blocks_output_until_pass} |"
        )
    lines.extend(["", "Evidence checks:"])
    for check in report.evidence_checks:
        status = "PASS" if check.ok else "FAIL"
        lines.append(f"- [{status}] {check.name}: {check.message or check.actual or ''}")
    if report.issues:
        lines.extend(["", "Issues:"])
        for issue in report.issues:
            lines.append(f"- [{issue.severity}] {issue.field}: {issue.message}")
    return "\n".join(lines)


def write_four_terminal_dc_command_review_json(
    report: FourTerminalDCCommandReview,
    output_path: str | Path,
) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
    return path


def _recipe_preflight_checks(recipe: FourTerminalDCRecipe) -> list[FourTerminalDCPreflightCheck]:
    return [
        FourTerminalDCPreflightCheck(
            name="measurement_geometry",
            ok=recipe.measurement_geometry.method == "four_terminal" and recipe.measurement_geometry.terminal_count == 4,
            expected="four_terminal, 4 terminals",
            actual=f"{recipe.measurement_geometry.method}, {recipe.measurement_geometry.terminal_count} terminals",
        ),
        FourTerminalDCPreflightCheck(
            name="dc_sense_mode",
            ok=recipe.dc_sense_mode == "remote_4wire",
            expected="remote_4wire",
            actual=recipe.dc_sense_mode,
        ),
        FourTerminalDCPreflightCheck(
            name="explicit_nplc",
            ok=recipe.instrument.nplc is not None,
            expected="instrument.nplc explicitly set",
            actual=str(recipe.instrument.nplc),
            message="NPLC is a measurement condition and must be deliberate.",
        ),
        FourTerminalDCPreflightCheck(
            name="explicit_ranges",
            ok=recipe.instrument.voltage_range_v is not None and recipe.instrument.current_range_a is not None,
            expected="voltage_range_v and current_range_a explicitly set",
            actual=f"voltage_range_v={recipe.instrument.voltage_range_v}, current_range_a={recipe.instrument.current_range_a}",
        ),
        FourTerminalDCPreflightCheck(
            name="explicit_compliance",
            ok=recipe.sweep.current_compliance_a is not None,
            expected="sweep.current_compliance_a explicitly set",
            actual=str(recipe.sweep.current_compliance_a),
        ),
        FourTerminalDCPreflightCheck(
            name="terminal_plane_match",
            ok=recipe.instrument.terminal is None or recipe.instrument.terminal == recipe.contacts.terminal_plane,
            expected=f"instrument.terminal matches contacts.terminal_plane={recipe.contacts.terminal_plane}",
            actual=f"instrument.terminal={recipe.instrument.terminal}",
        ),
        FourTerminalDCPreflightCheck(
            name="distinct_contacts",
            ok=len(
                {
                    recipe.contacts.source_contact,
                    recipe.contacts.drain_contact,
                    recipe.contacts.sense_hi_contact,
                    recipe.contacts.sense_lo_contact,
                }
            )
            == 4,
            expected="source, drain, sense_hi, sense_lo are all distinct",
            actual=", ".join(
                [
                    recipe.contacts.source_contact,
                    recipe.contacts.drain_contact,
                    recipe.contacts.sense_hi_contact,
                    recipe.contacts.sense_lo_contact,
                ]
            ),
        ),
    ]


def _hardware_preflight_checks(
    *,
    language: str | None,
    system_error: str | None,
    remote_sense_readback: str | None,
    readback_snapshot: dict[str, str | None],
) -> list[FourTerminalDCPreflightCheck]:
    checks = [
        FourTerminalDCPreflightCheck(
            name="keithley_command_set",
            ok=(language or "").upper() == "SCPI",
            expected="SCPI",
            actual=language,
        ),
        FourTerminalDCPreflightCheck(
            name="system_error_queue",
            ok=_is_no_error_text(system_error),
            expected="0, no error",
            actual=system_error,
        ),
        FourTerminalDCPreflightCheck(
            name="remote_sense_readback_available",
            ok=_readback_available(remote_sense_readback),
            expected="readable :SENS:CURR:RSEN? response",
            actual=remote_sense_readback,
        ),
    ]
    readback_fields = {
        "terminal_readback_available": "terminal",
        "nplc_readback_available": "current_nplc",
        "current_range_readback_available": "current_range",
        "voltage_range_readback_available": "voltage_range",
    }
    for check_name, field in readback_fields.items():
        value = readback_snapshot.get(field)
        checks.append(
            FourTerminalDCPreflightCheck(
                name=check_name,
                ok=_readback_available(value),
                expected=f"readable {field} query",
                actual=value,
            )
        )
    return checks


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    return str(value).strip()


def _is_no_error_text(value: str | None) -> bool:
    if value is None:
        return False
    text = value.strip()
    return text.startswith("0,") or text.upper().startswith("+0,")


def _readback_available(value: str | None) -> bool:
    if value is None:
        return False
    return not value.upper().startswith("ERROR")


def _validate_four_terminal_dc_against_safety(recipe: FourTerminalDCRecipe, safety: SafetyPreset) -> None:
    max_recipe_voltage = max(abs(voltage) for voltage in sweep_voltages(recipe.sweep))
    if max_recipe_voltage > safety.max_abs_voltage_v:
        raise SafetyLimitError(
            (
                f"Four-terminal DC sweep reaches {max_recipe_voltage:g} V, "
                f"above safety limit {safety.max_abs_voltage_v:g} V"
            ),
            triggered_limit="max_abs_voltage_v",
        )
    if recipe.sweep.current_compliance_a > safety.max_abs_current_a:
        raise SafetyLimitError(
            (
                f"Four-terminal DC compliance {recipe.sweep.current_compliance_a:g} A, "
                f"above safety limit {safety.max_abs_current_a:g} A"
            ),
            triggered_limit="max_abs_current_a",
        )


FOUR_TERMINAL_DC_ACTIVE_APPROVAL_GATES = (
    "four-terminal-dc-validate passes for the exact recipe",
    "four-terminal-dc-preflight hardware JSON exists and passed with SCPI mode",
    "remote-sense readback query :SENS:CURR:RSEN? was readable on the lab Keithley",
    "four-terminal-dc --dry-run completed and metadata NPLC/ranges/compliance match the recipe",
    "operator confirms force/sense contacts and terminal plane before any output",
    "active runner still performs output-off and zero-before-off cleanup in finally",
)


def _four_terminal_dc_active_command_steps(recipe: FourTerminalDCRecipe) -> tuple[FourTerminalDCCommandStep, ...]:
    source_delay = 0 if recipe.instrument.source_delay_s is None else recipe.instrument.source_delay_s
    return (
        FourTerminalDCCommandStep(1, "connect", "*IDN?", "identify the connected instrument", "MODEL 2450", True),
        FourTerminalDCCommandStep(2, "connect", "*LANG?", "require Keithley SCPI command set", "SCPI", True),
        FourTerminalDCCommandStep(3, "safe_start", ":OUTP OFF", "force output off before configuration"),
        FourTerminalDCCommandStep(4, "safe_start", "*RST", "reset known instrument state before four-terminal setup"),
        FourTerminalDCCommandStep(5, "safe_start", "*CLS", "clear stale command errors before checked writes"),
        FourTerminalDCCommandStep(6, "configure", f":ROUT:TERM {recipe.contacts.terminal_plane}", "select declared terminal plane", ":ROUT:TERM?", True),
        FourTerminalDCCommandStep(7, "configure", ':SENS:FUNC "CURR"', "measure current during Drain I-V", ":SENS:FUNC?", True),
        FourTerminalDCCommandStep(8, "configure", f":SENS:CURR:NPLC {recipe.instrument.nplc}", "set deliberate current integration time", ":SENS:CURR:NPLC?", True),
        FourTerminalDCCommandStep(9, "configure", f":SENS:CURR:RANG {recipe.instrument.current_range_a}", "set explicit current range", ":SENS:CURR:RANG?", True),
        FourTerminalDCCommandStep(10, "configure", ":SENS:CURR:RSEN ON", "enable current remote sense only after contact approval", ":SENS:CURR:RSEN?", True),
        FourTerminalDCCommandStep(11, "configure", ":SOUR:FUNC VOLT", "source drain voltage", ":SOUR:FUNC?", True),
        FourTerminalDCCommandStep(12, "configure", f":SOUR:VOLT:RANG {recipe.instrument.voltage_range_v}", "set explicit voltage range", ":SOUR:VOLT:RANG?", True),
        FourTerminalDCCommandStep(13, "configure", f":SOUR:VOLT:DEL {source_delay}", "set deliberate source delay", ":SOUR:VOLT:DEL?", True),
        FourTerminalDCCommandStep(14, "configure", ":SOUR:VOLT:READ:BACK ON", "enable source-voltage readback", ":SOUR:VOLT:READ:BACK?", True),
        FourTerminalDCCommandStep(15, "configure", f":SOUR:VOLT:ILIM {recipe.sweep.current_compliance_a}", "set current compliance with accepted ILIM/ILIMIT fallback", ":SOUR:VOLT:ILIM?", True),
        FourTerminalDCCommandStep(16, "pre_output", ":SOUR:VOLT 0", "start from zero drain bias before output"),
        FourTerminalDCCommandStep(17, "pre_output", ":SYST:ERR?", "require no command error before output", '0,"No error"', True),
        FourTerminalDCCommandStep(18, "pre_output", ":OUTP ON", "enable output only after all blocking readbacks pass"),
        FourTerminalDCCommandStep(19, "acquire", ":SOUR:VOLT <sweep_voltage>", "set each sweep voltage"),
        FourTerminalDCCommandStep(20, "acquire", ":READ?", "read current and compliance status"),
        FourTerminalDCCommandStep(21, "cleanup", ":SOUR:VOLT 0", "zero drain bias before output off"),
        FourTerminalDCCommandStep(22, "cleanup", ":OUTP OFF", "turn output off in normal/error/interrupt paths"),
        FourTerminalDCCommandStep(23, "cleanup", ":SENS:CURR:RSEN OFF", "disable current remote sense after output off", ":SENS:CURR:RSEN?"),
    )


def _active_command_evidence_checks(
    recipe: FourTerminalDCRecipe,
    *,
    preflight_json: str | Path | None,
    dry_run_metadata: str | Path | None,
) -> list[FourTerminalDCPreflightCheck]:
    checks: list[FourTerminalDCPreflightCheck] = [
        FourTerminalDCPreflightCheck(
            name="recipe_explicit_nplc",
            ok=recipe.instrument.nplc is not None,
            actual=str(recipe.instrument.nplc),
            message="Recipe declares Keithley NPLC.",
        ),
        FourTerminalDCPreflightCheck(
            name="recipe_explicit_ranges_and_compliance",
            ok=recipe.instrument.voltage_range_v is not None and recipe.instrument.current_range_a is not None and recipe.sweep.current_compliance_a is not None,
            actual=f"Vrange={recipe.instrument.voltage_range_v}, Irange={recipe.instrument.current_range_a}, compliance={recipe.sweep.current_compliance_a}",
            message="Recipe declares voltage range, current range, and compliance.",
        ),
    ]
    checks.extend(_preflight_json_evidence_checks(preflight_json))
    checks.extend(_dry_run_metadata_evidence_checks(recipe, dry_run_metadata))
    return checks


def _preflight_json_evidence_checks(preflight_json: str | Path | None) -> list[FourTerminalDCPreflightCheck]:
    if preflight_json is None:
        return [
            FourTerminalDCPreflightCheck(
                name="hardware_preflight_json_attached",
                ok=False,
                message="No hardware preflight JSON was attached.",
            )
        ]
    payload = _load_json_object(Path(preflight_json))
    checks_by_name = {check.get("name"): check for check in payload.get("checks", []) if isinstance(check, dict)}
    return [
        FourTerminalDCPreflightCheck(
            name="hardware_preflight_passed",
            ok=payload.get("preflight_passed") is True and payload.get("hardware_checked") is True,
            actual=f"preflight_passed={payload.get('preflight_passed')}, hardware_checked={payload.get('hardware_checked')}",
            message="Hardware preflight passed on an attached report.",
        ),
        FourTerminalDCPreflightCheck(
            name="hardware_preflight_keeps_output_blocked",
            ok=payload.get("active_hardware_run_allowed") is False,
            actual=str(payload.get("active_hardware_run_allowed")),
            message="Attached preflight did not authorize active output.",
        ),
        FourTerminalDCPreflightCheck(
            name="hardware_preflight_remote_sense_readback",
            ok=bool(checks_by_name.get("remote_sense_readback_available", {}).get("ok")),
            actual=str(checks_by_name.get("remote_sense_readback_available", {}).get("actual")),
            message="Attached preflight shows :SENS:CURR:RSEN? is readable.",
        ),
    ]


def _dry_run_metadata_evidence_checks(
    recipe: FourTerminalDCRecipe,
    dry_run_metadata: str | Path | None,
) -> list[FourTerminalDCPreflightCheck]:
    if dry_run_metadata is None:
        return [
            FourTerminalDCPreflightCheck(
                name="dry_run_metadata_attached",
                ok=False,
                message="No four-terminal DC dry-run metadata was attached.",
            )
        ]
    payload = _load_json_object(Path(dry_run_metadata))
    configured = payload.get("configured_smu", {}) if isinstance(payload.get("configured_smu"), dict) else {}
    remote_sense = payload.get("remote_sense", {}) if isinstance(payload.get("remote_sense"), dict) else {}
    nplc_matches = configured.get("nplc") == recipe.instrument.nplc
    return [
        FourTerminalDCPreflightCheck(
            name="dry_run_completed",
            ok=payload.get("completed") is True and payload.get("dry_run") is True,
            actual=f"completed={payload.get('completed')}, dry_run={payload.get('dry_run')}",
            message="Attached metadata is a completed four-terminal DC dry-run.",
        ),
        FourTerminalDCPreflightCheck(
            name="dry_run_measurement_type",
            ok=payload.get("measurement_type") == "four_terminal_dc",
            actual=str(payload.get("measurement_type")),
            message="Attached metadata belongs to the four-terminal DC method.",
        ),
        FourTerminalDCPreflightCheck(
            name="dry_run_nplc_matches_recipe",
            ok=nplc_matches,
            actual=f"metadata={configured.get('nplc')}, recipe={recipe.instrument.nplc}",
            message="Dry-run metadata preserves the recipe NPLC.",
        ),
        FourTerminalDCPreflightCheck(
            name="dry_run_remote_sense_not_configured",
            ok=remote_sense.get("configured_in_dry_run") is False,
            actual=str(remote_sense.get("configured_in_dry_run")),
            message="Dry-run did not configure Keithley remote sense.",
        ),
    ]


def _load_json_object(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _configure_remote_sense_checked(smu: Any, metadata: dict[str, Any]) -> None:
    configure = getattr(smu, "configure_current_remote_sense", None)
    readback = getattr(smu, "read_current_remote_sense", None)
    if configure is None or readback is None:
        raise SafetyLimitError(
            "SMU does not expose current remote-sense configuration/readback",
            "remote_sense_capability",
        )
    configure(True)
    metadata["remote_sense"]["configured"] = True
    response = str(readback()).strip()
    metadata["remote_sense"]["enabled_readback"] = response
    if response.upper().startswith("ERROR") or response.strip().upper() not in {"1", "ON", "TRUE"}:
        raise SafetyLimitError(
            f"Current remote-sense readback did not confirm ON: {response}",
            "remote_sense_readback",
        )
    metadata["remote_sense"]["enabled_readback_ok"] = True


def _disable_remote_sense_after_output_off(smu: Any, metadata: dict[str, Any]) -> None:
    remote = metadata.setdefault("remote_sense", {})
    remote["disabled_after_run_attempted"] = True
    configure = getattr(smu, "configure_current_remote_sense", None)
    readback = getattr(smu, "read_current_remote_sense", None)
    if configure is None:
        remote["disabled_after_run_error"] = "SMU does not expose configure_current_remote_sense"
        return
    try:
        configure(False)
        if readback is not None:
            remote["disabled_after_run_readback"] = str(readback()).strip()
    except Exception as exc:
        remote["disabled_after_run_error"] = f"{type(exc).__name__}: {exc}"


def _require_command_order(commands: list[str | None], earlier: str, later: str) -> None:
    try:
        earlier_index = commands.index(earlier)
        later_index = len(commands) - 1 - list(reversed(commands)).index(later)
    except ValueError as exc:
        raise ValueError(f"command-review JSON missing required command order item: {exc}") from exc
    if earlier_index >= later_index:
        raise ValueError(f"command-review JSON must list {earlier} before {later}")
