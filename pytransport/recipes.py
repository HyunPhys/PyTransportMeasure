"""YAML recipe and safety preset loading."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class InstrumentConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = "keithley_2450"
    address: str
    timeout_ms: int = Field(default=10000, gt=0)
    terminal: Literal["FRONT", "REAR"] | None = None
    voltage_range_v: float | None = Field(default=None, gt=0)
    current_range_a: float | None = Field(default=None, gt=0)


class LockInConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    id: Literal["srs_sr860"] = "srs_sr860"
    address: str | None = None
    timeout_ms: int = Field(default=10000, gt=0)
    channels: list[Literal["x", "y", "r", "theta"]] = Field(default_factory=lambda: ["x", "y", "r", "theta"])
    read_timing: Literal["after_dc_settle", "continuous", "external_trigger"] = "after_dc_settle"

    @model_validator(mode="after")
    def enabled_requires_address_and_channels(self) -> "LockInConfig":
        if self.enabled and not self.address:
            raise ValueError("enabled lock-in config requires address")
        if self.enabled and not self.channels:
            raise ValueError("enabled lock-in config requires at least one channel")
        return self


class SweepConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["linear_one_way", "forward_backward", "multi_segment"] = "linear_one_way"
    start_v: float | None = None
    stop_v: float | None = None
    points: int | None = Field(default=None, gt=1)
    delay_s: float = Field(default=0.1, ge=0.0)
    current_compliance_a: float = Field(gt=0)
    segments: list["SweepSegment"] = Field(default_factory=list)

    @model_validator(mode="after")
    def required_fields_match_mode(self) -> "SweepConfig":
        if self.mode in {"linear_one_way", "forward_backward"}:
            if self.start_v is None or self.stop_v is None or self.points is None:
                raise ValueError("start_v, stop_v, and points are required for linear modes")
        if self.mode == "multi_segment" and not self.segments:
            raise ValueError("segments are required for multi_segment mode")
        if self.mode != "multi_segment" and self.segments:
            raise ValueError("segments are only allowed for multi_segment mode")
        return self


class SweepSegment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start_v: float
    stop_v: float
    points: int = Field(gt=1)
    delay_s: float | None = Field(default=None, ge=0.0)


class GateSweepConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start_v: float
    stop_v: float
    points: int = Field(gt=1)
    settle_s: float = Field(default=0.1, ge=0.0)
    current_compliance_a: float = Field(gt=0)


class PulseTrainConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base_v: float = 0.0
    amplitude_v: float
    width_s: float = Field(gt=0)
    period_s: float = Field(gt=0)
    count: int = Field(gt=0)
    current_compliance_a: float = Field(gt=0)
    acquisition: Literal["pulse_end"] = "pulse_end"

    @model_validator(mode="after")
    def period_must_cover_width(self) -> "PulseTrainConfig":
        if self.period_s < self.width_s:
            raise ValueError("period_s must be >= width_s")
        return self

    @property
    def duty_cycle(self) -> float:
        return self.width_s / self.period_s

    @property
    def total_on_time_s(self) -> float:
        return self.width_s * self.count


class PulseSafetyLimits(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_abs_pulse_v: float = Field(gt=0)
    max_pulse_width_s: float = Field(gt=0)
    max_duty_cycle: float = Field(gt=0, le=1)
    max_pulse_count: int = Field(gt=0)
    max_total_on_time_s: float = Field(gt=0)


class OutputConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    directory: Path = Path("data/raw")


class ExperimentMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sample_id: str | None = None
    device_id: str | None = None
    cooldown_id: str | None = None
    contact_geometry: str | None = None
    contact_notes: str | None = None
    lab_notebook_ref: str | None = None
    operator: str | None = None
    notes: str | None = None
    tags: list[str] = Field(default_factory=list)


class ResistanceCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    min_ohm: float | None = Field(default=None, gt=0)
    max_ohm: float | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def min_must_not_exceed_max(self) -> "ResistanceCheck":
        if self.min_ohm is not None and self.max_ohm is not None and self.min_ohm > self.max_ohm:
            raise ValueError("min_ohm must be <= max_ohm")
        return self


class QualityChecks(BaseModel):
    model_config = ConfigDict(extra="forbid")

    require_completed: bool = True
    min_points: int | None = Field(default=None, gt=0)
    fitted_resistance_ohm: ResistanceCheck | None = None


class DrainIVRecipe(BaseModel):
    model_config = ConfigDict(extra="forbid")

    measurement_name: str = Field(min_length=1)
    experiment: ExperimentMetadata = ExperimentMetadata()
    instrument: InstrumentConfig
    sweep: SweepConfig
    safety_preset: str = "nano_device_safe"
    output: OutputConfig = OutputConfig()
    checks: QualityChecks | None = None

    @field_validator("measurement_name")
    @classmethod
    def measurement_name_is_file_friendly(cls, value: str) -> str:
        forbidden = '<>:"/\\|?*'
        if any(char in value for char in forbidden):
            raise ValueError(f"measurement_name cannot contain any of {forbidden}")
        return value

    @model_validator(mode="after")
    def voltage_range_must_cover_sweep(self) -> "DrainIVRecipe":
        if self.instrument.voltage_range_v is None:
            return self
        voltages = sweep_voltages(self.sweep)
        max_sweep_voltage = max(abs(voltage) for voltage in voltages)
        if self.instrument.voltage_range_v < max_sweep_voltage:
            raise ValueError("instrument.voltage_range_v must cover sweep start_v/stop_v")
        return self


class SingleGateRecipe(BaseModel):
    model_config = ConfigDict(extra="forbid")

    measurement_name: str = Field(min_length=1)
    experiment: ExperimentMetadata = ExperimentMetadata()
    drain_instrument: InstrumentConfig
    gate_instrument: InstrumentConfig
    drain_sweep: SweepConfig
    gate_sweep: GateSweepConfig
    safety_preset: str = "nano_device_safe"
    output: OutputConfig = OutputConfig()
    checks: QualityChecks | None = None

    @field_validator("measurement_name")
    @classmethod
    def measurement_name_is_file_friendly(cls, value: str) -> str:
        forbidden = '<>:"/\\|?*'
        if any(char in value for char in forbidden):
            raise ValueError(f"measurement_name cannot contain any of {forbidden}")
        return value

    @model_validator(mode="after")
    def voltage_ranges_must_cover_sweeps(self) -> "SingleGateRecipe":
        if self.drain_instrument.voltage_range_v is not None:
            drain_voltages = sweep_voltages(self.drain_sweep)
            max_drain_voltage = max(abs(voltage) for voltage in drain_voltages)
            if self.drain_instrument.voltage_range_v < max_drain_voltage:
                raise ValueError("drain_instrument.voltage_range_v must cover drain_sweep")
        if self.gate_instrument.voltage_range_v is not None:
            gate_voltages = gate_voltages_from_config(self.gate_sweep)
            max_gate_voltage = max(abs(voltage) for voltage in gate_voltages)
            if self.gate_instrument.voltage_range_v < max_gate_voltage:
                raise ValueError("gate_instrument.voltage_range_v must cover gate_sweep")
        return self


class AcLockInRecipe(BaseModel):
    model_config = ConfigDict(extra="forbid")

    measurement_name: str = Field(min_length=1)
    experiment: ExperimentMetadata = ExperimentMetadata()
    source_instrument: InstrumentConfig
    lockin: LockInConfig
    bias_sweep: SweepConfig
    safety_preset: str = "nano_device_safe"
    output: OutputConfig = OutputConfig()
    checks: QualityChecks | None = None

    @field_validator("measurement_name")
    @classmethod
    def measurement_name_is_file_friendly(cls, value: str) -> str:
        forbidden = '<>:"/\\|?*'
        if any(char in value for char in forbidden):
            raise ValueError(f"measurement_name cannot contain any of {forbidden}")
        return value

    @model_validator(mode="after")
    def ranges_and_lockin_must_be_valid(self) -> "AcLockInRecipe":
        if not self.lockin.enabled:
            raise ValueError("ac_lockin recipes require lockin.enabled=true")
        if self.source_instrument.voltage_range_v is not None:
            voltages = sweep_voltages(self.bias_sweep)
            max_bias_voltage = max(abs(voltage) for voltage in voltages)
            if self.source_instrument.voltage_range_v < max_bias_voltage:
                raise ValueError("source_instrument.voltage_range_v must cover bias_sweep")
        return self


class PulseRecipe(BaseModel):
    model_config = ConfigDict(extra="forbid")

    measurement_name: str = Field(min_length=1)
    experiment: ExperimentMetadata = ExperimentMetadata()
    source_instrument: InstrumentConfig
    pulse: PulseTrainConfig
    pulse_limits: PulseSafetyLimits
    safety_preset: str = "nano_device_safe"
    output: OutputConfig = OutputConfig()
    checks: QualityChecks | None = None

    @field_validator("measurement_name")
    @classmethod
    def measurement_name_is_file_friendly(cls, value: str) -> str:
        forbidden = '<>:"/\\|?*'
        if any(char in value for char in forbidden):
            raise ValueError(f"measurement_name cannot contain any of {forbidden}")
        return value

    @model_validator(mode="after")
    def pulse_must_fit_declared_limits_and_range(self) -> "PulseRecipe":
        max_abs_voltage = max(abs(self.pulse.base_v), abs(self.pulse.amplitude_v))
        if max_abs_voltage > self.pulse_limits.max_abs_pulse_v:
            raise ValueError("pulse voltage exceeds pulse_limits.max_abs_pulse_v")
        if self.pulse.width_s > self.pulse_limits.max_pulse_width_s:
            raise ValueError("pulse width exceeds pulse_limits.max_pulse_width_s")
        if self.pulse.duty_cycle > self.pulse_limits.max_duty_cycle:
            raise ValueError("pulse duty cycle exceeds pulse_limits.max_duty_cycle")
        if self.pulse.count > self.pulse_limits.max_pulse_count:
            raise ValueError("pulse count exceeds pulse_limits.max_pulse_count")
        if self.pulse.total_on_time_s > self.pulse_limits.max_total_on_time_s:
            raise ValueError("pulse total on-time exceeds pulse_limits.max_total_on_time_s")
        if self.source_instrument.voltage_range_v is not None and self.source_instrument.voltage_range_v < max_abs_voltage:
            raise ValueError("source_instrument.voltage_range_v must cover pulse voltage")
        return self


def linear_space(start: float, stop: float, points: int) -> list[float]:
    if points < 2:
        raise ValueError("points must be >= 2")
    step = (stop - start) / (points - 1)
    return [start + step * index for index in range(points)]


def sweep_voltages(sweep: SweepConfig) -> list[float]:
    if sweep.mode == "linear_one_way":
        return linear_space(float(sweep.start_v), float(sweep.stop_v), int(sweep.points))
    if sweep.mode == "forward_backward":
        forward = linear_space(float(sweep.start_v), float(sweep.stop_v), int(sweep.points))
        backward = linear_space(float(sweep.stop_v), float(sweep.start_v), int(sweep.points))[1:]
        return forward + backward
    voltages: list[float] = []
    for segment in sweep.segments:
        segment_voltages = linear_space(segment.start_v, segment.stop_v, segment.points)
        if voltages and segment_voltages and voltages[-1] == segment_voltages[0]:
            voltages.extend(segment_voltages[1:])
        else:
            voltages.extend(segment_voltages)
    return voltages


def sweep_delays(sweep: SweepConfig) -> list[float]:
    if sweep.mode in {"linear_one_way", "forward_backward"}:
        return [sweep.delay_s] * len(sweep_voltages(sweep))
    delays: list[float] = []
    last_voltage: float | None = None
    for segment in sweep.segments:
        segment_delay = sweep.delay_s if segment.delay_s is None else segment.delay_s
        segment_voltages = sweep_voltages_for_segment(segment)
        if last_voltage is not None and segment_voltages and last_voltage == segment_voltages[0]:
            segment_voltages = segment_voltages[1:]
        delays.extend([segment_delay] * len(segment_voltages))
        if segment_voltages:
            last_voltage = segment_voltages[-1]
    return delays


def sweep_voltages_for_segment(segment: SweepSegment) -> list[float]:
    return linear_space(segment.start_v, segment.stop_v, segment.points)


def gate_voltages_from_config(sweep: GateSweepConfig) -> list[float]:
    return linear_space(sweep.start_v, sweep.stop_v, sweep.points)


class SafetyPreset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    max_abs_voltage_v: float = Field(gt=0)
    max_abs_current_a: float = Field(gt=0)
    default_current_compliance_a: float = Field(gt=0)
    description: str = ""

    @model_validator(mode="after")
    def compliance_must_fit_current_limit(self) -> "SafetyPreset":
        if self.default_current_compliance_a > self.max_abs_current_a:
            raise ValueError("default_current_compliance_a must be <= max_abs_current_a")
        return self


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return data


def load_recipe(path: str | Path) -> DrainIVRecipe:
    return DrainIVRecipe.model_validate(load_yaml(Path(path)))


def load_single_gate_recipe(path: str | Path) -> SingleGateRecipe:
    return SingleGateRecipe.model_validate(load_yaml(Path(path)))


def load_ac_lockin_recipe(path: str | Path) -> AcLockInRecipe:
    return AcLockInRecipe.model_validate(load_yaml(Path(path)))


def load_pulse_recipe(path: str | Path) -> PulseRecipe:
    return PulseRecipe.model_validate(load_yaml(Path(path)))


def load_safety_preset(path: str | Path) -> SafetyPreset:
    return SafetyPreset.model_validate(load_yaml(Path(path)))


def load_named_safety_preset(name: str, search_dir: str | Path = "configs/safety") -> SafetyPreset:
    path = Path(search_dir) / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Safety preset not found: {path}")
    preset = load_safety_preset(path)
    if preset.name != name:
        raise ValueError(f"Safety preset file {path} has name={preset.name!r}, expected {name!r}")
    return preset
