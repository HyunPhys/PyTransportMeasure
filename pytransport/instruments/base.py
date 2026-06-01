"""Common instrument protocols."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class SMUVoltageSourceConfig:
    current_compliance_a: float
    voltage_range_v: float | None = None
    current_range_a: float | None = None
    terminal: str | None = None


@dataclass(frozen=True)
class LockInReading:
    x_v: float | None = None
    y_v: float | None = None
    r_v: float | None = None
    theta_deg: float | None = None

    def to_dict(self) -> dict[str, float | None]:
        return {
            "lockin_x_v": self.x_v,
            "lockin_y_v": self.y_v,
            "lockin_r_v": self.r_v,
            "lockin_theta_deg": self.theta_deg,
        }


class SourceMeasureUnit(Protocol):
    def connect(self) -> None:
        ...

    def identify(self) -> str:
        ...

    def probe(self) -> dict[str, str]:
        ...

    def configure_voltage_source(self, config: SMUVoltageSourceConfig) -> None:
        ...

    def set_voltage(self, voltage_v: float) -> None:
        ...

    def measure_current(self) -> tuple[float, bool]:
        ...

    def output_on(self) -> None:
        ...

    def output_off(self) -> None:
        ...

    def close(self) -> None:
        ...


class LockInAmplifier(Protocol):
    def connect(self) -> None:
        ...

    def identify(self) -> str:
        ...

    def probe(self) -> dict[str, str]:
        ...

    def read_channels(self) -> LockInReading:
        ...

    def close(self) -> None:
        ...
