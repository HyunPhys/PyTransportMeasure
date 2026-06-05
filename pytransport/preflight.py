"""Preflight checks before a hardware measurement."""

from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
from typing import Any, Callable

from .instruments.keithley_2450 import Keithley2450
from .instruments.srs_sr860 import probe_srs_sr860
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
class LockInSettingCheck:
    field: str
    expected: str
    actual: str | None
    ok: bool


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

    @property
    def ok(self) -> bool:
        return (
            self.validation_ok
            and self.distinct_addresses
            and self.source.ok
            and self.lockin.ok
            and lockin_settings_ok(self.lockin_settings)
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
    lockin_settings: tuple[LockInSettingCheck, ...] = ()

    @property
    def ok(self) -> bool:
        return (
            self.validation_ok
            and self.distinct_addresses
            and self.gate1.ok
            and self.gate2.ok
            and self.lockin.ok
            and lockin_settings_ok(self.lockin_settings)
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
) -> AcLockInPreflightReport:
    recipe = load_ac_lockin_recipe(recipe_path)
    return run_ac_lockin_preflight_for_recipe(
        recipe,
        recipe_path,
        safety_dir,
        resource_lister,
        source_probe_factory,
        lockin_probe_factory,
    )


def run_ac_lockin_preflight_for_recipe(
    recipe: AcLockInRecipe,
    recipe_path: str | Path,
    safety_dir: str | Path = "configs/safety",
    resource_lister: Callable[[], tuple[str, ...]] = list_resources,
    source_probe_factory: Callable[[str, int], dict[str, str]] | None = None,
    lockin_probe_factory: Callable[[str, int], dict[str, str]] | None = None,
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
    )


def run_dual_gate_lockin_preflight(
    recipe_path: str | Path,
    safety_dir: str | Path = "configs/safety",
    resource_lister: Callable[[], tuple[str, ...]] = list_resources,
    gate_probe_factory: Callable[[str, int], dict[str, str]] | None = None,
    lockin_probe_factory: Callable[[str, int], dict[str, str]] | None = None,
) -> DualGateLockInPreflightReport:
    recipe = load_dual_gate_lockin_recipe(recipe_path)
    return run_dual_gate_lockin_preflight_for_recipe(
        recipe,
        recipe_path,
        safety_dir,
        resource_lister,
        gate_probe_factory,
        lockin_probe_factory,
    )


def run_dual_gate_lockin_preflight_for_recipe(
    recipe: DualGateLockInRecipe,
    recipe_path: str | Path,
    safety_dir: str | Path = "configs/safety",
    resource_lister: Callable[[], tuple[str, ...]] = list_resources,
    gate_probe_factory: Callable[[str, int], dict[str, str]] | None = None,
    lockin_probe_factory: Callable[[str, int], dict[str, str]] | None = None,
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
        lockin_settings=compare_lockin_settings(recipe.lockin.model_dump(mode="json"), lockin.probe),
    )


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


def lockin_settings_ok(checks: tuple[LockInSettingCheck, ...]) -> bool:
    return all(check.ok for check in checks)


def compare_lockin_settings(lockin: dict[str, Any], probe: dict[str, str] | None) -> tuple[LockInSettingCheck, ...]:
    checks: list[LockInSettingCheck] = []
    for field, expected in expected_lockin_settings(lockin).items():
        actual = None if probe is None else probe.get(f"setting_{lockin_probe_setting_key(field)}")
        checks.append(
            LockInSettingCheck(
                field=field,
                expected=str(expected),
                actual=actual,
                ok=lockin_setting_matches(field, expected, actual),
            )
        )
    return tuple(checks)


def lockin_probe_setting_key(field: str) -> str:
    if field == "filter_slope_db_per_oct":
        return "filter_slope_index"
    return field


def expected_lockin_settings(lockin: dict[str, Any]) -> dict[str, Any]:
    expected: dict[str, Any] = {}
    for field in [
        "reference_source",
        "reference_frequency_hz",
        "sine_output_amplitude_v",
        "input_mode",
        "voltage_input",
        "input_coupling",
        "input_grounding",
        "voltage_input_range_v",
        "sensitivity_index",
        "time_constant_index",
        "filter_slope_db_per_oct",
        "synchronous_filter",
    ]:
        value = lockin.get(field)
        if value is not None:
            expected[field] = value
    return expected


def lockin_setting_matches(field: str, expected: Any, actual: str | None) -> bool:
    if actual is None:
        return False
    actual_text = actual.strip()
    if field in {"reference_frequency_hz", "sine_output_amplitude_v"}:
        try:
            return math.isclose(float(actual_text), float(expected), rel_tol=1e-6, abs_tol=1e-12)
        except ValueError:
            return False
    expected_code = expected_lockin_setting_code(field, expected)
    if expected_code is None:
        return False
    return normalize_setting_token(actual_text) == normalize_setting_token(expected_code)


def expected_lockin_setting_code(field: str, expected: Any) -> str | None:
    mappings = {
        "reference_source": {"internal": "0", "external": "1", "dual": "2", "chop": "3"},
        "input_mode": {"voltage": "0", "current": "1"},
        "voltage_input": {"a": "0", "a-b": "1"},
        "input_coupling": {"ac": "0", "dc": "1"},
        "input_grounding": {"float": "0", "ground": "1"},
        "voltage_input_range_v": {1.0: "0", 0.3: "1", 0.1: "2", 0.03: "3", 0.01: "4"},
        "filter_slope_db_per_oct": {6: "0", 12: "1", 18: "2", 24: "3"},
        "synchronous_filter": {False: "0", True: "1"},
    }
    if field in {"sensitivity_index", "time_constant_index"}:
        return str(int(expected))
    mapping = mappings.get(field)
    if mapping is None:
        return None
    return mapping.get(expected)


def normalize_setting_token(value: str) -> str:
    token = value.strip().lower().replace("_", "").replace("-", "")
    aliases = {
        "int": "0",
        "internal": "0",
        "ext": "1",
        "external": "1",
        "dual": "2",
        "chop": "3",
        "voltage": "0",
        "volt": "0",
        "current": "1",
        "curr": "1",
        "a": "0",
        "ab": "1",
        "ac": "0",
        "dc": "1",
        "float": "0",
        "flo": "0",
        "ground": "1",
        "gro": "1",
        "off": "0",
        "on": "1",
    }
    return aliases.get(token, token)


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
