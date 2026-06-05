"""Read-only SR860 setting comparison helpers."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Any

from .errors import SafetyLimitError


@dataclass(frozen=True)
class LockInSettingCheck:
    field: str
    expected: str
    actual: str | None
    ok: bool

    def to_dict(self) -> dict[str, str | bool | None]:
        return asdict(self)


def lockin_settings_ok(checks: tuple[LockInSettingCheck, ...]) -> bool:
    return all(check.ok for check in checks)


def lockin_settings_readback_available(probe: dict[str, str] | None) -> bool:
    if probe is None:
        return False
    return any(str(key).startswith("setting_") for key in probe)


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


def lockin_setting_checks_to_dicts(checks: tuple[LockInSettingCheck, ...]) -> list[dict[str, str | bool | None]]:
    return [check.to_dict() for check in checks]


def raise_for_lockin_settings_mismatch(
    label: str,
    checks: tuple[LockInSettingCheck, ...],
    *,
    readback_available: bool,
) -> None:
    if not readback_available or lockin_settings_ok(checks):
        return
    failed = [check for check in checks if not check.ok]
    details = "; ".join(
        f"{check.field} expected {check.expected} got {check.actual}" for check in failed[:4]
    )
    raise SafetyLimitError(
        f"{label} settings readback mismatch before output on: {details}",
        triggered_limit=f"{label}_settings_readback",
    )


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

