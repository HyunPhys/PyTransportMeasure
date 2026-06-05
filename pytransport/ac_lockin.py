"""AC / lock-in bias-sweep dry-run runner."""

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
from .instruments.base import LockInAmplifier, SMUVoltageSourceConfig, SourceMeasureUnit
from .io import unique_run_dir
from .recipes import AcLockInRecipe, SafetyPreset, sweep_delays, sweep_voltages
from .safety import validate_ac_lockin_recipe_against_safety, validate_point_current


AC_LOCKIN_COLUMNS = [
    "index",
    "bias_voltage_v",
    "source_current_a",
    "elapsed_s",
    "source_resistance_ohm",
    "source_compliance_hit",
    "lockin_x_v",
    "lockin_y_v",
    "lockin_r_v",
    "lockin_theta_deg",
]


@dataclass(frozen=True)
class AcLockInPoint:
    index: int
    bias_voltage_v: float
    source_current_a: float
    elapsed_s: float
    source_resistance_ohm: float | None
    source_compliance_hit: bool
    lockin_x_v: float | None
    lockin_y_v: float | None
    lockin_r_v: float | None
    lockin_theta_deg: float | None

    def to_dict(self) -> dict[str, float | int | bool | None]:
        return asdict(self)


class AcLockInRunWriter:
    def __init__(self, output_dir: Path, measurement_name: str):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.run_dir = unique_run_dir(output_dir, f"{timestamp}_{safe_name(measurement_name)}")
        self.run_dir.mkdir(parents=True, exist_ok=False)
        self.csv_path = self.run_dir / "points.csv"
        self.metadata_path = self.run_dir / "metadata.json"
        self.recipe_snapshot_path = self.run_dir / "recipe_snapshot.yaml"
        self.safety_snapshot_path = self.run_dir / "safety_snapshot.yaml"
        self._csv_file = self.csv_path.open("w", newline="", encoding="utf-8")
        self._writer = csv.DictWriter(self._csv_file, fieldnames=AC_LOCKIN_COLUMNS)
        self._writer.writeheader()
        self._csv_file.flush()

    def write_point(self, point: AcLockInPoint) -> None:
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


def ac_lockin_point_count(recipe: AcLockInRecipe) -> int:
    return len(sweep_voltages(recipe.bias_sweep))


def format_ac_lockin_plan(
    recipe: AcLockInRecipe,
    safety: SafetyPreset,
    recipe_path: str | Path,
    preview_points: int = 5,
) -> str:
    voltages = sweep_voltages(recipe.bias_sweep)
    lines = [
        f"AC Lock-In Sweep Plan: {recipe.measurement_name}",
        f"Recipe: {Path(recipe_path)}",
        f"Measurement geometry: {format_geometry(recipe.measurement_geometry.model_dump(mode='json'))}",
        f"Safety preset: {safety.name}",
        f"Source instrument: {recipe.source_instrument.id} at {recipe.source_instrument.address}",
        f"Source NPLC: {recipe.source_instrument.nplc if recipe.source_instrument.nplc is not None else 'auto'}",
        f"Lock-in: {recipe.lockin.id} at {recipe.lockin.address}",
        f"Lock-in channels: {', '.join(recipe.lockin.channels)}",
        f"Lock-in timing: {recipe.lockin.read_timing}",
        f"Bias sweep: {voltages[0]:.6g} V -> {voltages[-1]:.6g} V, {len(voltages)} points, mode {recipe.bias_sweep.mode}",
        f"Source compliance: {recipe.bias_sweep.current_compliance_a:.6g} A",
        f"Safety current limit: {safety.max_abs_current_a:.6g} A",
    ]
    preview = max(0, preview_points)
    if preview:
        head = voltages[:preview]
        tail = voltages[-preview:] if len(voltages) > preview else []
        lines.append("Preview points:")
        for index, voltage in enumerate(head):
            lines.append(f"  #{index}: Vbias={voltage:.6g} V")
        if tail and tail[0] != head[0]:
            if len(voltages) > 2 * preview:
                lines.append("  ...")
            start_index = len(voltages) - len(tail)
            for offset, voltage in enumerate(tail):
                lines.append(f"  #{start_index + offset}: Vbias={voltage:.6g} V")
    return "\n".join(lines)


def format_geometry(geometry: dict) -> str:
    method = geometry.get("method") or "two_terminal"
    terminal_count = geometry.get("terminal_count") or 2
    notes = geometry.get("notes")
    text = f"{method}, {terminal_count}-terminal"
    return f"{text}, {notes}" if notes else text


def run_ac_lockin_sweep(
    recipe: AcLockInRecipe,
    safety: SafetyPreset,
    source_smu: SourceMeasureUnit,
    lockin: LockInAmplifier,
    recipe_path: str | Path | None = None,
    progress_callback: Callable[[AcLockInPoint, int], None] | None = None,
) -> dict[str, Any]:
    validate_ac_lockin_recipe_against_safety(recipe, safety)
    writer = AcLockInRunWriter(Path(recipe.output.directory), recipe.measurement_name)
    writer.write_yaml_snapshot(writer.recipe_snapshot_path, recipe.model_dump(mode="json"))
    writer.write_yaml_snapshot(writer.safety_snapshot_path, safety.model_dump(mode="json"))
    points_written = 0
    metadata: dict[str, Any] = {
        "measurement_name": recipe.measurement_name,
        "measurement_type": "ac_lockin_sweep",
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
        "lockin_probe": None,
        "csv_path": str(writer.csv_path),
        "metadata_path": str(writer.metadata_path),
        "recipe_snapshot_path": str(writer.recipe_snapshot_path),
        "safety_snapshot_path": str(writer.safety_snapshot_path),
    }

    try:
        source_smu.connect()
        lockin.connect()
        metadata["source_instrument_probe"] = source_smu.probe()
        metadata["lockin_probe"] = lockin.probe()
        source_smu.configure_voltage_source(
            SMUVoltageSourceConfig(
                current_compliance_a=recipe.bias_sweep.current_compliance_a,
                voltage_range_v=recipe.source_instrument.voltage_range_v,
                current_range_a=recipe.source_instrument.current_range_a,
                terminal=recipe.source_instrument.terminal,
                nplc=recipe.source_instrument.nplc,
            )
        )
        source_smu.output_on()

        start = time.monotonic()
        voltages = sweep_voltages(recipe.bias_sweep)
        delays = sweep_delays(recipe.bias_sweep)
        for index, (voltage_v, delay_s) in enumerate(zip(voltages, delays)):
            source_smu.set_voltage(float(voltage_v))
            if delay_s:
                time.sleep(delay_s)
            source_current_a, compliance_hit = source_smu.measure_current()
            if compliance_hit:
                raise SafetyLimitError("Source instrument compliance was reached", "source_instrument_compliance")
            validate_point_current(source_current_a, safety)
            reading = lockin.read_channels()
            source_resistance_ohm = None if source_current_a == 0 else float(voltage_v) / source_current_a
            point = AcLockInPoint(
                index=index,
                bias_voltage_v=float(voltage_v),
                source_current_a=float(source_current_a),
                elapsed_s=time.monotonic() - start,
                source_resistance_ohm=source_resistance_ohm,
                source_compliance_hit=compliance_hit,
                lockin_x_v=reading.x_v,
                lockin_y_v=reading.y_v,
                lockin_r_v=reading.r_v,
                lockin_theta_deg=reading.theta_deg,
            )
            writer.write_point(point)
            points_written += 1
            if progress_callback is not None:
                progress_callback(point, len(voltages))

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
            source_smu.output_off()
        finally:
            try:
                source_smu.close()
            finally:
                lockin.close()
                metadata["finished_at"] = datetime.now().isoformat(timespec="seconds")
                metadata["points_written"] = points_written
                writer.write_metadata(metadata)
                writer.close()
