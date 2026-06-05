"""Lock-in timing helpers shared by lock-in measurement runners."""

from __future__ import annotations

from typing import Any


SR860_TIME_CONSTANTS_S: tuple[float, ...] = (
    1e-6,
    3e-6,
    10e-6,
    30e-6,
    100e-6,
    300e-6,
    1e-3,
    3e-3,
    10e-3,
    30e-3,
    100e-3,
    300e-3,
    1.0,
    3.0,
    10.0,
    30.0,
    100.0,
    300.0,
    1000.0,
    3000.0,
    10000.0,
    30000.0,
)


def sr860_time_constant_s(index: int | None) -> float | None:
    if index is None:
        return None
    return SR860_TIME_CONSTANTS_S[index]


def lockin_read_settle_s(lockin: Any) -> float:
    explicit = _get(lockin, "read_settle_s")
    if explicit is not None:
        return float(explicit)

    multiplier = _get(lockin, "settle_time_constants")
    time_constant_index = _get(lockin, "time_constant_index")
    if multiplier is None or time_constant_index is None:
        return 0.0
    time_constant_s = sr860_time_constant_s(int(time_constant_index))
    if time_constant_s is None:
        return 0.0
    return float(multiplier) * time_constant_s


def lockin_time_constant_s(lockin: Any) -> float | None:
    index = _get(lockin, "time_constant_index")
    return sr860_time_constant_s(None if index is None else int(index))


def _get(source: Any, key: str) -> Any:
    if isinstance(source, dict):
        return source.get(key)
    return getattr(source, key, None)
