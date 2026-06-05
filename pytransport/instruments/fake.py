"""Dry-run SMU implementation."""

from __future__ import annotations

import random
import math
from dataclasses import dataclass

from .base import LockInReading, SMUVoltageSourceConfig


def fake_voltage_source_config_readback(config: SMUVoltageSourceConfig | None) -> dict[str, str | None]:
    if config is None:
        return {
            "source_function": None,
            "sense_function": None,
            "terminal": None,
            "current_nplc": None,
            "current_range": None,
            "current_range_auto": None,
            "voltage_range": None,
            "voltage_readback": None,
            "source_current_limit": None,
        }
    return {
        "source_function": "VOLT",
        "sense_function": "CURR",
        "terminal": config.terminal,
        "current_nplc": None if config.nplc is None else f"{config.nplc:.12g}",
        "current_range": None if config.current_range_a is None else f"{config.current_range_a:.12g}",
        "current_range_auto": "1" if config.current_range_a is None else "0",
        "voltage_range": None if config.voltage_range_v is None else f"{config.voltage_range_v:.12g}",
        "voltage_readback": "1",
        "source_current_limit": f"{config.current_compliance_a:.12g}",
    }


class FakeSMU:
    def __init__(self, resistance_ohm: float = 10_000_000.0, noise_std_a: float = 1e-10):
        self.resistance_ohm = resistance_ohm
        self.noise_std_a = noise_std_a
        self.voltage_v = 0.0
        self.current_compliance_a = 1e-6
        self.is_output_on = False
        self.connected = False
        self.last_voltage_source_config: SMUVoltageSourceConfig | None = None

    def connect(self) -> None:
        self.connected = True

    def identify(self) -> str:
        return "FAKE,SMU,DRY-RUN,0"

    def probe(self) -> dict[str, str]:
        return {
            "address": "FAKE",
            "idn": self.identify(),
            "language": "SIM",
            "system_error": '0,"No error"',
            "simulated_resistance_ohm": f"{self.resistance_ohm:.12g}",
            "noise_std_a": f"{self.noise_std_a:.12g}",
        }

    def configure_voltage_source(self, config: SMUVoltageSourceConfig) -> None:
        self.last_voltage_source_config = config
        self.current_compliance_a = config.current_compliance_a

    def read_voltage_source_config(self) -> dict[str, str | None]:
        return fake_voltage_source_config_readback(self.last_voltage_source_config)

    def set_voltage(self, voltage_v: float) -> None:
        self.voltage_v = voltage_v

    def measure_current(self) -> tuple[float, bool]:
        ideal_current = self.voltage_v / self.resistance_ohm
        measured = ideal_current + random.gauss(0.0, self.noise_std_a)
        compliance_hit = abs(measured) >= self.current_compliance_a
        return measured, compliance_hit

    def output_on(self) -> None:
        self.is_output_on = True

    def output_off(self) -> None:
        self.is_output_on = False

    def close(self) -> None:
        self.connected = False


@dataclass
class CoupledFakeDeviceState:
    drain_voltage_v: float = 0.0
    gate_voltage_v: float = 0.0
    channel_resistance_ohm: float = 10_000.0
    gate_leak_resistance_ohm: float = 1_000_000_000.0
    gate_modulation_per_v: float = 0.0
    noise_std_a: float = 1e-10


@dataclass
class DualGateFakeDeviceState:
    drain_voltage_v: float = 0.0
    gate1_voltage_v: float = 0.0
    gate2_voltage_v: float = 0.0
    channel_resistance_ohm: float = 10_000.0
    gate1_leak_resistance_ohm: float = 1_000_000_000.0
    gate2_leak_resistance_ohm: float = 1_000_000_000.0
    gate1_modulation_per_v: float = 0.0
    gate2_modulation_per_v: float = 0.0
    cross_term_per_v2: float = 0.0
    noise_std_a: float = 1e-10


class CoupledFakeSMU:
    def __init__(self, role: str, state: CoupledFakeDeviceState):
        if role not in {"drain", "gate"}:
            raise ValueError("role must be 'drain' or 'gate'")
        self.role = role
        self.state = state
        self.current_compliance_a = 1e-6
        self.is_output_on = False
        self.connected = False
        self.last_voltage_source_config: SMUVoltageSourceConfig | None = None

    def connect(self) -> None:
        self.connected = True

    def identify(self) -> str:
        return f"FAKE,{self.role.upper()}-SMU,DRY-RUN,0"

    def probe(self) -> dict[str, str]:
        return {
            "address": f"FAKE::{self.role.upper()}",
            "idn": self.identify(),
            "language": "SIM",
            "system_error": '0,"No error"',
            "channel_resistance_ohm": f"{self.state.channel_resistance_ohm:.12g}",
            "gate_leak_resistance_ohm": f"{self.state.gate_leak_resistance_ohm:.12g}",
            "gate_modulation_per_v": f"{self.state.gate_modulation_per_v:.12g}",
            "noise_std_a": f"{self.state.noise_std_a:.12g}",
        }

    def configure_voltage_source(self, config: SMUVoltageSourceConfig) -> None:
        self.last_voltage_source_config = config
        self.current_compliance_a = config.current_compliance_a

    def read_voltage_source_config(self) -> dict[str, str | None]:
        return fake_voltage_source_config_readback(self.last_voltage_source_config)

    def set_voltage(self, voltage_v: float) -> None:
        if self.role == "drain":
            self.state.drain_voltage_v = voltage_v
        else:
            self.state.gate_voltage_v = voltage_v

    def measure_current(self) -> tuple[float, bool]:
        if self.role == "gate":
            ideal_current = self.state.gate_voltage_v / self.state.gate_leak_resistance_ohm
        else:
            conductance_scale = max(0.0, 1.0 + self.state.gate_modulation_per_v * self.state.gate_voltage_v)
            ideal_current = self.state.drain_voltage_v / self.state.channel_resistance_ohm * conductance_scale
        measured = ideal_current + random.gauss(0.0, self.state.noise_std_a)
        compliance_hit = abs(measured) >= self.current_compliance_a
        return measured, compliance_hit

    def output_on(self) -> None:
        self.is_output_on = True

    def output_off(self) -> None:
        self.is_output_on = False

    def close(self) -> None:
        self.connected = False


class DualGateFakeSMU:
    def __init__(self, role: str, state: DualGateFakeDeviceState):
        if role not in {"drain", "gate1", "gate2"}:
            raise ValueError("role must be 'drain', 'gate1', or 'gate2'")
        self.role = role
        self.state = state
        self.current_compliance_a = 1e-6
        self.is_output_on = False
        self.connected = False
        self.last_voltage_source_config: SMUVoltageSourceConfig | None = None

    def connect(self) -> None:
        self.connected = True

    def identify(self) -> str:
        return f"FAKE,{self.role.upper()}-SMU,DRY-RUN,0"

    def probe(self) -> dict[str, str]:
        return {
            "address": f"FAKE::{self.role.upper()}",
            "idn": self.identify(),
            "language": "SIM",
            "system_error": '0,"No error"',
            "channel_resistance_ohm": f"{self.state.channel_resistance_ohm:.12g}",
            "gate1_leak_resistance_ohm": f"{self.state.gate1_leak_resistance_ohm:.12g}",
            "gate2_leak_resistance_ohm": f"{self.state.gate2_leak_resistance_ohm:.12g}",
            "gate1_modulation_per_v": f"{self.state.gate1_modulation_per_v:.12g}",
            "gate2_modulation_per_v": f"{self.state.gate2_modulation_per_v:.12g}",
            "cross_term_per_v2": f"{self.state.cross_term_per_v2:.12g}",
            "noise_std_a": f"{self.state.noise_std_a:.12g}",
        }

    def configure_voltage_source(self, config: SMUVoltageSourceConfig) -> None:
        self.last_voltage_source_config = config
        self.current_compliance_a = config.current_compliance_a

    def read_voltage_source_config(self) -> dict[str, str | None]:
        return fake_voltage_source_config_readback(self.last_voltage_source_config)

    def set_voltage(self, voltage_v: float) -> None:
        if self.role == "drain":
            self.state.drain_voltage_v = voltage_v
        elif self.role == "gate1":
            self.state.gate1_voltage_v = voltage_v
        else:
            self.state.gate2_voltage_v = voltage_v

    def measure_current(self) -> tuple[float, bool]:
        if self.role == "gate1":
            ideal_current = self.state.gate1_voltage_v / self.state.gate1_leak_resistance_ohm
        elif self.role == "gate2":
            ideal_current = self.state.gate2_voltage_v / self.state.gate2_leak_resistance_ohm
        else:
            conductance_scale = max(
                0.0,
                1.0
                + self.state.gate1_modulation_per_v * self.state.gate1_voltage_v
                + self.state.gate2_modulation_per_v * self.state.gate2_voltage_v
                + self.state.cross_term_per_v2 * self.state.gate1_voltage_v * self.state.gate2_voltage_v,
            )
            ideal_current = self.state.drain_voltage_v / self.state.channel_resistance_ohm * conductance_scale
        measured = ideal_current + random.gauss(0.0, self.state.noise_std_a)
        compliance_hit = abs(measured) >= self.current_compliance_a
        return measured, compliance_hit

    def output_on(self) -> None:
        self.is_output_on = True

    def output_off(self) -> None:
        self.is_output_on = False

    def close(self) -> None:
        self.connected = False


class DualGateFakeLockIn:
    def __init__(
        self,
        state: DualGateFakeDeviceState,
        base_r_v: float = 1e-6,
        gate1_sensitivity_v_per_v: float = 0.0,
        gate2_sensitivity_v_per_v: float = 0.0,
        cross_sensitivity_v_per_v2: float = 0.0,
        phase_deg: float = 0.0,
        noise_std_v: float = 0.0,
    ):
        if base_r_v < 0:
            raise ValueError("base_r_v must be >= 0")
        if noise_std_v < 0:
            raise ValueError("noise_std_v must be >= 0")
        self.state = state
        self.base_r_v = base_r_v
        self.gate1_sensitivity_v_per_v = gate1_sensitivity_v_per_v
        self.gate2_sensitivity_v_per_v = gate2_sensitivity_v_per_v
        self.cross_sensitivity_v_per_v2 = cross_sensitivity_v_per_v2
        self.phase_deg = phase_deg
        self.noise_std_v = noise_std_v
        self.connected = False

    def connect(self) -> None:
        self.connected = True

    def identify(self) -> str:
        return "FAKE,LOCKIN,DUAL-GATE-SR860-DRY-RUN,0"

    def probe(self) -> dict[str, str]:
        return {
            "address": "FAKE::LOCKIN",
            "idn": self.identify(),
            "base_r_v": f"{self.base_r_v:.12g}",
            "gate1_sensitivity_v_per_v": f"{self.gate1_sensitivity_v_per_v:.12g}",
            "gate2_sensitivity_v_per_v": f"{self.gate2_sensitivity_v_per_v:.12g}",
            "cross_sensitivity_v_per_v2": f"{self.cross_sensitivity_v_per_v2:.12g}",
            "phase_deg": f"{self.phase_deg:.12g}",
            "noise_std_v": f"{self.noise_std_v:.12g}",
        }

    def read_channels(self) -> LockInReading:
        signal_r_v = max(
            0.0,
            self.base_r_v
            + self.gate1_sensitivity_v_per_v * self.state.gate1_voltage_v
            + self.gate2_sensitivity_v_per_v * self.state.gate2_voltage_v
            + self.cross_sensitivity_v_per_v2 * self.state.gate1_voltage_v * self.state.gate2_voltage_v,
        )
        phase_rad = math.radians(self.phase_deg)
        x_v = signal_r_v * math.cos(phase_rad) + random.gauss(0.0, self.noise_std_v)
        y_v = signal_r_v * math.sin(phase_rad) + random.gauss(0.0, self.noise_std_v)
        r_v = math.hypot(x_v, y_v)
        theta_deg = math.degrees(math.atan2(y_v, x_v))
        return LockInReading(x_v=x_v, y_v=y_v, r_v=r_v, theta_deg=theta_deg)

    def close(self) -> None:
        self.connected = False


class FakeLockIn:
    def __init__(
        self,
        signal_r_v: float = 1e-6,
        phase_deg: float = 0.0,
        noise_std_v: float = 0.0,
    ):
        if signal_r_v < 0:
            raise ValueError("signal_r_v must be >= 0")
        if noise_std_v < 0:
            raise ValueError("noise_std_v must be >= 0")
        self.signal_r_v = signal_r_v
        self.phase_deg = phase_deg
        self.noise_std_v = noise_std_v
        self.connected = False

    def connect(self) -> None:
        self.connected = True

    def identify(self) -> str:
        return "FAKE,LOCKIN,SR860-DRY-RUN,0"

    def probe(self) -> dict[str, str]:
        return {
            "address": "FAKE::LOCKIN",
            "idn": self.identify(),
            "simulated_signal_r_v": f"{self.signal_r_v:.12g}",
            "simulated_phase_deg": f"{self.phase_deg:.12g}",
            "noise_std_v": f"{self.noise_std_v:.12g}",
        }

    def read_channels(self) -> LockInReading:
        phase_rad = math.radians(self.phase_deg)
        x_v = self.signal_r_v * math.cos(phase_rad) + random.gauss(0.0, self.noise_std_v)
        y_v = self.signal_r_v * math.sin(phase_rad) + random.gauss(0.0, self.noise_std_v)
        r_v = math.hypot(x_v, y_v)
        theta_deg = math.degrees(math.atan2(y_v, x_v))
        return LockInReading(x_v=x_v, y_v=y_v, r_v=r_v, theta_deg=theta_deg)

    def close(self) -> None:
        self.connected = False
