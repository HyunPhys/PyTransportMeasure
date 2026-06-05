"""Shared SMU configuration builders and metadata snapshots."""

from __future__ import annotations

from dataclasses import asdict
import math
from typing import Any

from .errors import SafetyLimitError
from .instruments.base import SMUVoltageSourceConfig


def build_voltage_source_config(instrument: Any, current_compliance_a: float) -> SMUVoltageSourceConfig:
    return SMUVoltageSourceConfig(
        current_compliance_a=float(current_compliance_a),
        voltage_range_v=_optional_float(_get(instrument, "voltage_range_v")),
        current_range_a=_optional_float(_get(instrument, "current_range_a")),
        terminal=_get(instrument, "terminal"),
        nplc=_optional_float(_get(instrument, "nplc")),
    )


def voltage_source_config_snapshot(config: SMUVoltageSourceConfig) -> dict[str, float | str | None]:
    return asdict(config)


def read_voltage_source_config_if_available(smu: Any) -> dict[str, str | None] | None:
    reader = getattr(smu, "read_voltage_source_config", None)
    if reader is None:
        return None
    try:
        return reader()
    except Exception as exc:
        return {"readback_error": f"{type(exc).__name__}: {exc}"}


def compare_voltage_source_config_readback(
    expected: SMUVoltageSourceConfig,
    readback: dict[str, str | None] | None,
) -> dict[str, Any]:
    if readback is None:
        return {"available": False, "matched": None, "checks": []}

    checks = [
        _check_text("source_function", "VOLT", readback.get("source_function"), mode="contains"),
        _check_text("sense_function", "CURR", readback.get("sense_function"), mode="contains"),
        _check_text("voltage_readback", "1", readback.get("voltage_readback"), mode="bool_on"),
        _check_float("source_current_limit", expected.current_compliance_a, readback.get("source_current_limit")),
    ]
    if expected.terminal is not None:
        checks.append(_check_text("terminal", expected.terminal, readback.get("terminal"), mode="terminal"))
    if expected.nplc is not None:
        checks.append(_check_float("current_nplc", expected.nplc, readback.get("current_nplc")))
    if expected.voltage_range_v is not None:
        checks.append(_check_float("voltage_range", expected.voltage_range_v, readback.get("voltage_range")))
    if expected.current_range_a is None:
        checks.append(_check_text("current_range_auto", "1", readback.get("current_range_auto"), mode="bool_on"))
    else:
        checks.append(_check_float("current_range", expected.current_range_a, readback.get("current_range")))
        checks.append(_check_text("current_range_auto", "0", readback.get("current_range_auto"), mode="bool_off"))

    matched = all(check["matched"] for check in checks)
    return {"available": True, "matched": matched, "checks": checks}


def raise_for_voltage_source_config_readback_mismatch(label: str, check: dict[str, Any]) -> None:
    if check.get("matched") is not False:
        return
    failed = [item for item in check.get("checks", []) if not item.get("matched")]
    details = "; ".join(f"{item['field']} expected {item['expected']} got {item['actual']}" for item in failed[:4])
    raise SafetyLimitError(
        f"{label} SMU configuration readback mismatch before output on: {details}",
        triggered_limit=f"{label}_smu_config_readback",
    )


def _check_float(field: str, expected: float, actual: str | None) -> dict[str, Any]:
    actual_float = _parse_float(actual)
    matched = actual_float is not None and math.isclose(actual_float, float(expected), rel_tol=1e-4, abs_tol=1e-12)
    return {
        "field": field,
        "expected": float(expected),
        "actual": actual,
        "matched": matched,
    }


def _check_text(field: str, expected: str, actual: str | None, mode: str) -> dict[str, Any]:
    actual_norm = "" if actual is None else str(actual).strip().strip('"').upper()
    expected_norm = str(expected).strip().strip('"').upper()
    if actual_norm.startswith("ERROR"):
        matched = False
    elif mode == "contains":
        matched = expected_norm in actual_norm
    elif mode == "terminal":
        matched = actual_norm.startswith(expected_norm[:4])
    elif mode == "bool_on":
        matched = actual_norm in {"1", "ON", "TRUE"}
    elif mode == "bool_off":
        matched = actual_norm in {"0", "OFF", "FALSE"}
    else:
        matched = actual_norm == expected_norm
    return {
        "field": field,
        "expected": expected,
        "actual": actual,
        "matched": matched,
    }


def _parse_float(value: str | None) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if text.upper().startswith("ERROR"):
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _get(source: Any, key: str) -> Any:
    if isinstance(source, dict):
        return source.get(key)
    return getattr(source, key, None)


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)
