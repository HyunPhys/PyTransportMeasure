"""Shared SMU configuration builders and metadata snapshots."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

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


def _get(source: Any, key: str) -> Any:
    if isinstance(source, dict):
        return source.get(key)
    return getattr(source, key, None)


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)
