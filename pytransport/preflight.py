"""Preflight checks before a hardware measurement."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .instruments.keithley_2450 import Keithley2450
from .instruments.srs_sr860 import probe_srs_sr860
from .lockin_settings import (
    LockInSettingCheck,
    compare_lockin_settings,
    lockin_settings_ok,
)
from .sr860_config import (
    check_sr860_configure_evidence,
    format_sr860_configure_evidence_check,
    load_sr860_configure_json,
)
from .dual_gate_lockin import format_dual_gate_lockin_scan_readiness
from .recipes import (
    AcLockInRecipe,
    DrainIVRecipe,
    DualGateLockInRecipe,
    SingleGateRecipe,
    load_ac_lockin_recipe,
    load_dual_gate_lockin_recipe,
    load_named_safety_preset,
    load_recipe,
    load_single_gate_recipe,
)
from .safety import (
    validate_ac_lockin_recipe_against_safety,
    validate_dual_gate_lockin_recipe_against_safety,
    validate_single_gate_recipe_against_safety,
)
from .validation import RecipeValidationReport, format_validation_report, validate_recipe
from .visa_utils import list_resources


@dataclass(frozen=True)
class PreflightReport:
    validation: RecipeValidationReport
    visa_resources: tuple[str, ...]
    address_found: bool
    probe: dict[str, str] | None
    probe_error: str | None

    @property
    def ok(self) -> bool:
        return self.address_found and self.probe_error is None and self.probe is not None


@dataclass(frozen=True)
class InstrumentPreflight:
    label: str
    address: str
    address_found: bool
    probe: dict[str, str] | None
    probe_error: str | None

    @property
    def ok(self) -> bool:
        return self.address_found and self.probe_error is None and self.probe is not None


@dataclass(frozen=True)
class SingleGatePreflightReport:
    recipe_path: str
    validation_ok: bool
    validation_error: str | None
    visa_resources: tuple[str, ...]
    distinct_addresses: bool
    drain: InstrumentPreflight
    gate: InstrumentPreflight

    @property
    def ok(self) -> bool:
        return self.validation_ok and self.distinct_addresses and self.drain.ok and self.gate.ok


@dataclass(frozen=True)
class AcLockInPreflightReport:
    recipe_path: str
    validation_ok: bool
    validation_error: str | None
    visa_resources: tuple[str, ...]
    distinct_addresses: bool
    source: InstrumentPreflight
    lockin: InstrumentPreflight
    lockin_settings: tuple[LockInSettingCheck, ...] = ()
    sr860_configure_evidence: dict[str, Any] | None = None

    @property
    def ok(self) -> bool:
        return (
            self.validation_ok
            and self.distinct_addresses
            and self.source.ok
            and self.lockin.ok
            and lockin_settings_ok(self.lockin_settings)
            and evidence_check_ok(self.sr860_configure_evidence)
        )


@dataclass(frozen=True)
class DualGateLockInPreflightReport:
    recipe_path: str
    validation_ok: bool
    validation_error: str | None
    visa_resources: tuple[str, ...]
    distinct_addresses: bool
    topology_lines: tuple[str, ...]
    gate1: InstrumentPreflight
    gate2: InstrumentPreflight
    lockin: InstrumentPreflight
    scan_readiness_lines: tuple[str, ...] = ()
    lockin_settings: tuple[LockInSettingCheck, ...] = ()
    sr860_configure_evidence: dict[str, Any] | None = None

    @property
    def ok(self) -> bool:
        return (
            self.validation_ok
            and self.distinct_addresses
            and self.gate1.ok
            and self.gate2.ok
            and self.lockin.ok
            and lockin_settings_ok(self.lockin_settings)
            and evidence_check_ok(self.sr860_configure_evidence)
        )


def run_preflight(
    recipe_path: str | Path,
    safety_dir: str | Path = "configs/safety",
    resource_lister: Callable[[], tuple[str, ...]] = list_resources,
    probe_factory: Callable[[str, int], dict[str, str]] | None = None,
) -> PreflightReport:
    recipe = load_recipe(recipe_path)
    return run_preflight_for_recipe(recipe, recipe_path, safety_dir, resource_lister, probe_factory)


def run_preflight_for_recipe(
    recipe: DrainIVRecipe,
    recipe_path: str | Path,
    safety_dir: str | Path = "configs/safety",
    resource_lister: Callable[[], tuple[str, ...]] = list_resources,
    probe_factory: Callable[[str, int], dict[str, str]] | None = None,
) -> PreflightReport:
    safety = load_named_safety_preset(recipe.safety_preset, safety_dir)
    validation = validate_recipe(recipe, safety, recipe_path)
    resources = resource_lister()
    address_found = recipe.instrument.address in resources
    probe = None
    probe_error = None
    if address_found:
        try:
            if probe_factory is None:
                probe = probe_keithley(recipe.instrument.address, recipe.instrument.timeout_ms)
            else:
                probe = probe_factory(recipe.instrument.address, recipe.instrument.timeout_ms)
        except Exception as exc:
            probe_error = f"{type(exc).__name__}: {exc}"
    return PreflightReport(
        validation=validation,
        visa_resources=resources,
        address_found=address_found,
        probe=probe,
        probe_error=probe_error,
    )


def run_single_gate_preflight(
    recipe_path: str | Path,
    safety_dir: str | Path = "configs/safety",
    resource_lister: Callable[[], tuple[str, ...]] = list_resources,
    probe_factory: Callable[[str, int], dict[str, str]] | None = None,
) -> SingleGatePreflightReport:
    recipe = load_single_gate_recipe(recipe_path)
    return run_single_gate_preflight_for_recipe(recipe, recipe_path, safety_dir, resource_lister, probe_factory)


def run_single_gate_preflight_for_recipe(
    recipe: SingleGateRecipe,
    recipe_path: str | Path,
    safety_dir: str | Path = "configs/safety",
    resource_lister: Callable[[], tuple[str, ...]] = list_resources,
    probe_factory: Callable[[str, int], dict[str, str]] | None = None,
) -> SingleGatePreflightReport:
    validation_ok = True
    validation_error = None
    try:
        safety = load_named_safety_preset(recipe.safety_preset, safety_dir)
        validate_single_gate_recipe_against_safety(recipe, safety)
    except Exception as exc:
        validation_ok = False
        validation_error = f"{type(exc).__name__}: {exc}"
    resources = resource_lister()
    distinct_addresses = recipe.drain_instrument.address != recipe.gate_instrument.address
    drain = run_instrument_preflight(
        "drain",
        recipe.drain_instrument.address,
        recipe.drain_instrument.timeout_ms,
        resources,
        probe_factory,
    )
    gate = run_instrument_preflight(
        "gate",
        recipe.gate_instrument.address,
        recipe.gate_instrument.timeout_ms,
        resources,
        probe_factory,
    )
    return SingleGatePreflightReport(
        recipe_path=str(recipe_path),
        validation_ok=validation_ok,
        validation_error=validation_error,
        visa_resources=resources,
        distinct_addresses=distinct_addresses,
        drain=drain,
        gate=gate,
    )


def run_ac_lockin_preflight(
    recipe_path: str | Path,
    safety_dir: str | Path = "configs/safety",
    resource_lister: Callable[[], tuple[str, ...]] = list_resources,
    source_probe_factory: Callable[[str, int], dict[str, str]] | None = None,
    lockin_probe_factory: Callable[[str, int], dict[str, str]] | None = None,
    sr860_configure_json: str | Path | None = None,
) -> AcLockInPreflightReport:
    recipe = load_ac_lockin_recipe(recipe_path)
    return run_ac_lockin_preflight_for_recipe(
        recipe,
        recipe_path,
        safety_dir,
        resource_lister,
        source_probe_factory,
        lockin_probe_factory,
        sr860_configure_json,
    )


def run_ac_lockin_preflight_for_recipe(
    recipe: AcLockInRecipe,
    recipe_path: str | Path,
    safety_dir: str | Path = "configs/safety",
    resource_lister: Callable[[], tuple[str, ...]] = list_resources,
    source_probe_factory: Callable[[str, int], dict[str, str]] | None = None,
    lockin_probe_factory: Callable[[str, int], dict[str, str]] | None = None,
    sr860_configure_json: str | Path | None = None,
) -> AcLockInPreflightReport:
    validation_ok = True
    validation_error = None
    try:
        safety = load_named_safety_preset(recipe.safety_preset, safety_dir)
        validate_ac_lockin_recipe_against_safety(recipe, safety)
    except Exception as exc:
        validation_ok = False
        validation_error = f"{type(exc).__name__}: {exc}"
    resources = resource_lister()
    lockin_address = recipe.lockin.address or ""
    distinct_addresses = recipe.source_instrument.address != lockin_address
    source = run_instrument_preflight(
        "source",
        recipe.source_instrument.address,
        recipe.source_instrument.timeout_ms,
        resources,
        source_probe_factory,
    )
    lockin = run_instrument_preflight(
        "lock-in",
        lockin_address,
        recipe.lockin.timeout_ms,
        resources,
        lockin_probe_factory or probe_srs_sr860,
    )
    return AcLockInPreflightReport(
        recipe_path=str(recipe_path),
        validation_ok=validation_ok,
        validation_error=validation_error,
        visa_resources=resources,
        distinct_addresses=distinct_addresses,
        source=source,
        lockin=lockin,
        lockin_settings=compare_lockin_settings(recipe.lockin.model_dump(mode="json"), lockin.probe),
        sr860_configure_evidence=build_sr860_configure_evidence_check(recipe, sr860_configure_json),
    )


def run_dual_gate_lockin_preflight(
    recipe_path: str | Path,
    safety_dir: str | Path = "configs/safety",
    resource_lister: Callable[[], tuple[str, ...]] = list_resources,
    gate_probe_factory: Callable[[str, int], dict[str, str]] | None = None,
    lockin_probe_factory: Callable[[str, int], dict[str, str]] | None = None,
    sr860_configure_json: str | Path | None = None,
) -> DualGateLockInPreflightReport:
    recipe = load_dual_gate_lockin_recipe(recipe_path)
    return run_dual_gate_lockin_preflight_for_recipe(
        recipe,
        recipe_path,
        safety_dir,
        resource_lister,
        gate_probe_factory,
        lockin_probe_factory,
        sr860_configure_json,
    )


def run_dual_gate_lockin_preflight_for_recipe(
    recipe: DualGateLockInRecipe,
    recipe_path: str | Path,
    safety_dir: str | Path = "configs/safety",
    resource_lister: Callable[[], tuple[str, ...]] = list_resources,
    gate_probe_factory: Callable[[str, int], dict[str, str]] | None = None,
    lockin_probe_factory: Callable[[str, int], dict[str, str]] | None = None,
    sr860_configure_json: str | Path | None = None,
) -> DualGateLockInPreflightReport:
    validation_ok = True
    validation_error = None
    try:
        safety = load_named_safety_preset(recipe.safety_preset, safety_dir)
        validate_dual_gate_lockin_recipe_against_safety(recipe, safety)
    except Exception as exc:
        validation_ok = False
        validation_error = f"{type(exc).__name__}: {exc}"
    resources = resource_lister()
    lockin_address = recipe.lockin.address or ""
    addresses = [recipe.gate1_instrument.address, recipe.gate2_instrument.address, lockin_address]
    distinct_addresses = len(set(addresses)) == len(addresses)
    gate1 = run_instrument_preflight(
        "gate1",
        recipe.gate1_instrument.address,
        recipe.gate1_instrument.timeout_ms,
        resources,
        gate_probe_factory,
    )
    gate2 = run_instrument_preflight(
        "gate2",
        recipe.gate2_instrument.address,
        recipe.gate2_instrument.timeout_ms,
        resources,
        gate_probe_factory,
    )
    lockin = run_instrument_preflight(
        "lock-in",
        lockin_address,
        recipe.lockin.timeout_ms,
        resources,
        lockin_probe_factory or probe_srs_sr860,
    )
    return DualGateLockInPreflightReport(
        recipe_path=str(recipe_path),
        validation_ok=validation_ok,
        validation_error=validation_error,
        visa_resources=resources,
        distinct_addresses=distinct_addresses,
        topology_lines=format_dual_gate_lockin_topology_lines(recipe),
        gate1=gate1,
        gate2=gate2,
        lockin=lockin,
        scan_readiness_lines=tuple(format_dual_gate_lockin_scan_readiness(recipe)),
        lockin_settings=compare_lockin_settings(recipe.lockin.model_dump(mode="json"), lockin.probe),
        sr860_configure_evidence=build_sr860_configure_evidence_check(recipe, sr860_configure_json),
    )


def build_sr860_configure_evidence_check(recipe: Any, sr860_configure_json: str | Path | None) -> dict[str, Any] | None:
    if sr860_configure_json is None:
        return None
    try:
        payload = check_sr860_configure_evidence(recipe, load_sr860_configure_json(sr860_configure_json))
        return {"path": str(sr860_configure_json), **payload}
    except Exception as exc:
        return {
            "schema": "pytransport.sr860_configure_evidence_check.v1",
            "path": str(sr860_configure_json),
            "ok": False,
            "expected_command_count": None,
            "transcript_command_count": None,
            "checks": [
                {
                    "name": "load_configure_json",
                    "passed": False,
                    "message": f"{type(exc).__name__}: {exc}",
                }
            ],
        }


def evidence_check_ok(payload: dict[str, Any] | None) -> bool:
    return True if payload is None else payload.get("ok") is True


def run_instrument_preflight(
    label: str,
    address: str,
    timeout_ms: int,
    resources: tuple[str, ...],
    probe_factory: Callable[[str, int], dict[str, str]] | None = None,
) -> InstrumentPreflight:
    address_found = address in resources
    probe = None
    probe_error = None
    if address_found:
        try:
            if probe_factory is None:
                probe = probe_keithley(address, timeout_ms)
            else:
                probe = probe_factory(address, timeout_ms)
        except Exception as exc:
            probe_error = f"{type(exc).__name__}: {exc}"
    return InstrumentPreflight(
        label=label,
        address=address,
        address_found=address_found,
        probe=probe,
        probe_error=probe_error,
    )


def format_dual_gate_lockin_topology_lines(recipe: DualGateLockInRecipe) -> tuple[str, ...]:
    topology = recipe.topology
    lines = [
        f"Layout: {topology.device_layout}",
        f"Gate roles: gate1={topology.gate1_role}, gate2={topology.gate2_role}",
        f"Source/drain: {topology.source_contact} -> {topology.drain_contact}",
        f"Lock-in input: {topology.lockin_input_mode} on {', '.join(topology.lockin_input_contacts)}",
        f"Excitation source: {topology.excitation_source}",
    ]
    if topology.excitation_contacts:
        lines.append(f"Excitation contacts: {', '.join(topology.excitation_contacts)}")
    if topology.excitation_amplitude_v is not None:
        lines.append(f"Excitation amplitude: {topology.excitation_amplitude_v:g} V")
    if topology.current_bias_resistor_ohm is not None:
        lines.append(f"Current-bias resistor: {topology.current_bias_resistor_ohm:g} ohm")
    if topology.notes:
        lines.append(f"Notes: {topology.notes}")
    return tuple(lines)


def probe_keithley(address: str, timeout_ms: int) -> dict[str, str]:
    smu = Keithley2450(address, timeout_ms)
    try:
        smu.connect()
        return smu.probe()
    finally:
        smu.close()


def format_preflight_report(report: PreflightReport) -> str:
    lines = [
        "Preflight",
        "",
        format_validation_report(report.validation),
        "",
        "VISA resources:",
    ]
    if report.visa_resources:
        lines.extend(f"- {resource}" for resource in report.visa_resources)
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            f"Recipe address found: {report.address_found}",
            "Probe:",
        ]
    )
    if report.probe is not None:
        lines.extend(f"- {key}: {value}" for key, value in report.probe.items())
    elif report.probe_error is not None:
        lines.append(f"- error: {report.probe_error}")
    else:
        lines.append("- skipped")
    lines.extend(["", f"Preflight OK: {report.ok}"])
    return "\n".join(lines)


def format_single_gate_preflight_report(report: SingleGatePreflightReport) -> str:
    lines = [
        "Single-Gate Preflight",
        "",
        f"Recipe: {report.recipe_path}",
        f"Validation OK: {report.validation_ok}",
    ]
    if report.validation_error is not None:
        lines.append(f"Validation error: {report.validation_error}")
    lines.extend(["", "VISA resources:"])
    if report.visa_resources:
        lines.extend(f"- {resource}" for resource in report.visa_resources)
    else:
        lines.append("- none")
    lines.extend(["", f"Drain/gate addresses distinct: {report.distinct_addresses}"])
    for instrument in [report.drain, report.gate]:
        lines.extend(
            [
                "",
                f"{instrument.label.capitalize()} instrument:",
                f"- address: {instrument.address}",
                f"- address found: {instrument.address_found}",
                "- probe:",
            ]
        )
        if instrument.probe is not None:
            lines.extend(f"  - {key}: {value}" for key, value in instrument.probe.items())
        elif instrument.probe_error is not None:
            lines.append(f"  - error: {instrument.probe_error}")
        else:
            lines.append("  - skipped")
        lines.append(f"- ok: {instrument.ok}")
    lines.extend(["", f"Single-gate preflight OK: {report.ok}"])
    return "\n".join(lines)


def format_ac_lockin_preflight_report(report: AcLockInPreflightReport) -> str:
    lines = [
        "AC Lock-In Preflight",
        "",
        f"Recipe: {report.recipe_path}",
        f"Validation OK: {report.validation_ok}",
    ]
    if report.validation_error is not None:
        lines.append(f"Validation error: {report.validation_error}")
    lines.extend(["", "VISA resources:"])
    if report.visa_resources:
        lines.extend(f"- {resource}" for resource in report.visa_resources)
    else:
        lines.append("- none")
    lines.extend(["", f"Source/lock-in addresses distinct: {report.distinct_addresses}"])
    for instrument in [report.source, report.lockin]:
        lines.extend(
            [
                "",
                f"{instrument.label.capitalize()} instrument:",
                f"- address: {instrument.address}",
                f"- address found: {instrument.address_found}",
                "- probe:",
            ]
        )
        if instrument.probe is not None:
            lines.extend(f"  - {key}: {value}" for key, value in instrument.probe.items())
        elif instrument.probe_error is not None:
            lines.append(f"  - error: {instrument.probe_error}")
        else:
            lines.append("  - skipped")
        lines.append(f"- ok: {instrument.ok}")
    lines.extend(format_lockin_setting_checks(report.lockin_settings))
    lines.extend(format_sr860_configure_evidence_section(report.sr860_configure_evidence))
    lines.extend(["", f"AC lock-in preflight OK: {report.ok}"])
    return "\n".join(lines)


def format_dual_gate_lockin_preflight_report(report: DualGateLockInPreflightReport) -> str:
    lines = [
        "Dual-Gate Lock-In Preflight",
        "",
        f"Recipe: {report.recipe_path}",
        f"Validation OK: {report.validation_ok}",
    ]
    if report.validation_error is not None:
        lines.append(f"Validation error: {report.validation_error}")
    if report.topology_lines:
        lines.extend(["", "Topology:"])
        lines.extend(f"- {line}" for line in report.topology_lines)
    if report.scan_readiness_lines:
        lines.extend(["", "Scan readiness:"])
        lines.extend(f"- {line.strip()}" for line in report.scan_readiness_lines[1:])
    lines.extend(["", "VISA resources:"])
    if report.visa_resources:
        lines.extend(f"- {resource}" for resource in report.visa_resources)
    else:
        lines.append("- none")
    lines.extend(["", f"Gate1/gate2/lock-in addresses distinct: {report.distinct_addresses}"])
    for instrument in [report.gate1, report.gate2, report.lockin]:
        lines.extend(
            [
                "",
                f"{instrument.label.capitalize()} instrument:",
                f"- address: {instrument.address}",
                f"- address found: {instrument.address_found}",
                "- probe:",
            ]
        )
        if instrument.probe is not None:
            lines.extend(f"  - {key}: {value}" for key, value in instrument.probe.items())
        elif instrument.probe_error is not None:
            lines.append(f"  - error: {instrument.probe_error}")
        else:
            lines.append("  - skipped")
        lines.append(f"- ok: {instrument.ok}")
    lines.extend(format_lockin_setting_checks(report.lockin_settings))
    lines.extend(format_sr860_configure_evidence_section(report.sr860_configure_evidence))
    lines.extend(["", f"Dual-gate lock-in preflight OK: {report.ok}"])
    return "\n".join(lines)


def format_lockin_setting_checks(checks: tuple[LockInSettingCheck, ...]) -> list[str]:
    if not checks:
        return ["", "Lock-in setting check:", "- no expected settings declared"]
    lines = ["", "Lock-in setting check:"]
    for check in checks:
        actual = check.actual if check.actual is not None else "missing"
        lines.append(
            f"- {check.field}: expected {check.expected}, actual {actual}, ok: {check.ok}"
        )
    lines.append(f"- all expected settings match: {lockin_settings_ok(checks)}")
    return lines


def format_sr860_configure_evidence_section(payload: dict[str, Any] | None) -> list[str]:
    if payload is None:
        return []
    return ["", format_sr860_configure_evidence_check(payload)]
