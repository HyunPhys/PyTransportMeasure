"""Shared measurement data models."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class MeasurementPoint:
    index: int
    voltage_v: float
    current_a: float
    elapsed_s: float
    resistance_ohm: float | None
    compliance_hit: bool = False

    def to_dict(self) -> dict[str, float | int | bool | None]:
        return asdict(self)
