"""Pulse measurement dry-run runner."""

from __future__ import annotations

import csv
import json
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import yaml

from .batch import safe_name
from .errors import SafetyLimitError
from .instruments.base import SMUVoltageSourceConfig, SourceMeasureUnit
from .io import unique_run_dir
from .recipes import PulseRecipe, SafetyPreset
from .safety import validate_point_current, validate_pulse_recipe_against_safety


PULSE_COLUMNS = [
    "index",
    "pulse_index",
    "base_voltage_v",
    "pulse_voltage_v",
    "width_s",
    "period_s",
    "duty_cycle",
    "source_current_a",
    "elapsed_s",
    "compliance_hit",
]


@dataclass(frozen=True)
class PulsePoint:
    index: int
    pulse_index: int
    base_voltage_v: float
    pulse_voltage_v: float
    width_s: float
    period_s: float
    duty_cycle: float
    source_current_a: float
    elapsed_s: float
    compliance_hit: bool

    def to_dict(self) -> dict[str, float | int | bool]:
        return asdict(self)


class PulseRunWriter:
    def __init__(self, output_dir: Path, measurement_name: str):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.run_dir = unique_run_dir(output_dir, f"{timestamp}_{safe_name(measurement_name)}")
        self.run_dir.mkdir(parents=True, exist_ok=False)
        self.csv_path = self.run_dir / "points.csv"
        self.metadata_path = self.run_dir / "metadata.json"
        self.recipe_snapshot_path = self.run_dir / "recipe_snapshot.yaml"
        self.safety_snapshot_path = self.run_dir / "safety_snapshot.yaml"
        self._csv_file = self.csv_path.open("w", newline="", encoding="utf-8")
        self._writer = csv.DictWriter(self._csv_file, fieldnames=PULSE_COLUMNS)
        self._writer.writeheader()
        self._csv_file.flush()

    def write_point(self, point: PulsePoint) -> None:
        self._writer.writerow(point.to_dict())
        self._csv_file.flush()

    def write_metadata(self, metadata: dict[str, Any]) -> None:
        with self.metadata_path.open("w", encoding="utf-8") as handle:
            json.dump(metadata, handle, indent=2, sort_keys=True, default=str)

    def write_yaml_snapshot(self, path: Path, data: dict[str, Any]) -> None:
        with path.open("w", encoding="utf-8") as handle:
            yaml.safe_dump(data, handle, sort_keys=False)

    def close(self) -> None:
        self._csv_file.close()


def pulse_point_count(recipe: PulseRecipe) -> int:
    return recipe.pulse.count


def format_pulse_plan(recipe: PulseRecipe, safety: SafetyPreset, recipe_path: str | Path, preview_points: int = 5) -> str:
    pulse = recipe.pulse
    lines = [
        f"Pulse Measurement Plan: {recipe.measurement_name}",
        f"Recipe: {Path(recipe_path)}",
        f"Measurement geometry: {format_geometry(recipe.measurement_geometry.model_dump(mode='json'))}",
        f"Safety preset: {safety.name}",
        f"Source instrument: {recipe.source_instrument.id} at {recipe.source_instrument.address}",
        f"Base voltage: {pulse.base_v:.6g} V",
        f"Pulse voltage: {pulse.amplitude_v:.6g} V",
        f"Pulse width: {pulse.width_s:.6g} s",
        f"Pulse period: {pulse.period_s:.6g} s",
        f"Duty cycle: {pulse.duty_cycle:.6g}",
        f"Pulse count: {pulse.count}",
        f"Total on-time: {pulse.total_on_time_s:.6g} s",
        f"Current compliance: {pulse.current_compliance_a:.6g} A",
        f"Acquisition: {pulse.acquisition}",
    ]
    preview = min(max(preview_points, 0), pulse.count)
    if preview:
        lines.append("Preview pulses:")
        for index in range(preview):
            lines.append(f"  #{index}: Vpulse={pulse.amplitude_v:.6g} V, width={pulse.width_s:.6g} s")
        if pulse.count > 2 * preview:
            lines.append("  ...")
        tail_start = max(preview, pulse.count - preview)
        for index in range(tail_start, pulse.count):
            lines.append(f"  #{index}: Vpulse={pulse.amplitude_v:.6g} V, width={pulse.width_s:.6g} s")
    return "\n".join(lines)


def format_geometry(geometry: dict) -> str:
    method = geometry.get("method") or "two_terminal"
    terminal_count = geometry.get("terminal_count") or 2
    notes = geometry.get("notes")
    text = f"{method}, {terminal_count}-terminal"
    return f"{text}, {notes}" if notes else text


def run_pulse_measurement(
    recipe: PulseRecipe,
    safety: SafetyPreset,
    source_smu: SourceMeasureUnit,
    recipe_path: str | Path | None = None,
    progress_callback: Callable[[PulsePoint, int], None] | None = None,
    sleep: bool = False,
) -> dict[str, Any]:
    validate_pulse_recipe_against_safety(recipe, safety)
    writer = PulseRunWriter(Path(recipe.output.directory), recipe.measurement_name)
    writer.write_yaml_snapshot(writer.recipe_snapshot_path, recipe.model_dump(mode="json"))
    writer.write_yaml_snapshot(writer.safety_snapshot_path, safety.model_dump(mode="json"))
    points_written = 0
    metadata: dict[str, Any] = {
        "measurement_name": recipe.measurement_name,
        "measurement_type": "pulse_measurement",
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "completed": False,
        "interrupted": False,
        "error_type": None,
        "error_message": None,
        "triggered_limit": None,
        "points_written": 0,
        "recipe": recipe.model_dump(mode="json"),
        "recipe_path": str(Path(recipe_path)) if recipe_path is not None else None,
        "safety": safety.model_dump(mode="json"),
        "run_dir": str(writer.run_dir),
        "source_instrument_probe": None,
        "csv_path": str(writer.csv_path),
        "metadata_path": str(writer.metadata_path),
        "recipe_snapshot_path": str(writer.recipe_snapshot_path),
        "safety_snapshot_path": str(writer.safety_snapshot_path),
    }
    pulse = recipe.pulse
    try:
        source_smu.connect()
        metadata["source_instrument_probe"] = source_smu.probe()
        source_smu.configure_voltage_source(
            SMUVoltageSourceConfig(
                current_compliance_a=pulse.current_compliance_a,
                voltage_range_v=recipe.source_instrument.voltage_range_v,
                current_range_a=recipe.source_instrument.current_range_a,
                terminal=recipe.source_instrument.terminal,
                nplc=recipe.source_instrument.nplc,
            )
        )
        source_smu.set_voltage(float(pulse.base_v))
        source_smu.output_on()
        start = time.monotonic()
        for index in range(pulse.count):
            source_smu.set_voltage(float(pulse.amplitude_v))
            if sleep:
                time.sleep(pulse.width_s)
            current_a, compliance_hit = source_smu.measure_current()
            if compliance_hit:
                raise SafetyLimitError("Pulse source compliance was reached", "pulse_source_compliance")
            validate_point_current(current_a, safety)
            source_smu.set_voltage(float(pulse.base_v))
            if sleep and pulse.period_s > pulse.width_s:
                time.sleep(pulse.period_s - pulse.width_s)
            point = PulsePoint(
                index=index,
                pulse_index=index,
                base_voltage_v=float(pulse.base_v),
                pulse_voltage_v=float(pulse.amplitude_v),
                width_s=float(pulse.width_s),
                period_s=float(pulse.period_s),
                duty_cycle=float(pulse.duty_cycle),
                source_current_a=float(current_a),
                elapsed_s=time.monotonic() - start,
                compliance_hit=compliance_hit,
            )
            writer.write_point(point)
            points_written += 1
            if progress_callback is not None:
                progress_callback(point, pulse.count)
        metadata["completed"] = True
        return metadata
    except SafetyLimitError as exc:
        metadata["error_type"] = type(exc).__name__
        metadata["error_message"] = str(exc)
        metadata["triggered_limit"] = exc.triggered_limit
        return metadata
    except KeyboardInterrupt:
        metadata["interrupted"] = True
        metadata["error_type"] = "KeyboardInterrupt"
        metadata["error_message"] = "Measurement interrupted by user"
        return metadata
    except Exception as exc:
        metadata["error_type"] = type(exc).__name__
        metadata["error_message"] = str(exc)
        return metadata
    finally:
        try:
            source_smu.set_voltage(float(recipe.pulse.base_v))
        finally:
            try:
                source_smu.output_off()
            finally:
                source_smu.close()
                metadata["finished_at"] = datetime.now().isoformat(timespec="seconds")
                metadata["points_written"] = points_written
                writer.write_metadata(metadata)
                writer.close()
