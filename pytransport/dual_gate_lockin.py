"""Dual-gate lock-in sweep runner.

Current milestone: dry-run execution for two Keithley gate biases plus SR860
lock-in readout. Hardware execution remains CLI-blocked until SR860 excitation
and wiring are smoke-tested.
"""

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
from .recipes import DualGateLockInRecipe, SafetyPreset, gate_voltages_from_config
from .safety import validate_dual_gate_lockin_recipe_against_safety, validate_point_current


DUAL_GATE_LOCKIN_COLUMNS = [
    "index",
    "gate1_index",
    "gate2_index",
    "gate1_voltage_v",
    "gate2_voltage_v",
    "gate1_current_a",
    "gate2_current_a",
    "elapsed_s",
    "gate1_compliance_hit",
    "gate2_compliance_hit",
    "lockin_x_v",
    "lockin_y_v",
    "lockin_r_v",
    "lockin_theta_deg",
]


@dataclass(frozen=True)
class DualGateLockInPoint:
    index: int
    gate1_index: int
    gate2_index: int
    gate1_voltage_v: float
    gate2_voltage_v: float
    gate1_current_a: float
    gate2_current_a: float
    elapsed_s: float
    gate1_compliance_hit: bool
    gate2_compliance_hit: bool
    lockin_x_v: float | None
    lockin_y_v: float | None
    lockin_r_v: float | None
    lockin_theta_deg: float | None

    def to_dict(self) -> dict[str, float | int | bool | None]:
        return asdict(self)


class DualGateLockInRunWriter:
    def __init__(self, output_dir: Path, measurement_name: str):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.run_dir = unique_run_dir(output_dir, f"{timestamp}_{safe_name(measurement_name)}")
        self.run_dir.mkdir(parents=True, exist_ok=False)
        self.csv_path = self.run_dir / "points.csv"
        self.metadata_path = self.run_dir / "metadata.json"
        self.recipe_snapshot_path = self.run_dir / "recipe_snapshot.yaml"
        self.safety_snapshot_path = self.run_dir / "safety_snapshot.yaml"
        self._csv_file = self.csv_path.open("w", newline="", encoding="utf-8")
        self._writer = csv.DictWriter(self._csv_file, fieldnames=DUAL_GATE_LOCKIN_COLUMNS)
        self._writer.writeheader()
        self._csv_file.flush()

    def write_point(self, point: DualGateLockInPoint) -> None:
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


def dual_gate_lockin_point_count(recipe: DualGateLockInRecipe) -> int:
    return len(gate_voltages_from_config(recipe.gate1_sweep)) * len(gate_voltages_from_config(recipe.gate2_sweep))


def format_dual_gate_lockin_plan(
    recipe: DualGateLockInRecipe,
    safety: SafetyPreset,
    recipe_path: str | Path,
    preview_points: int = 5,
) -> str:
    gate1_voltages = gate_voltages_from_config(recipe.gate1_sweep)
    gate2_voltages = gate_voltages_from_config(recipe.gate2_sweep)
    lines = [
        f"Dual-Gate Lock-In Sweep Plan: {recipe.measurement_name}",
        f"Recipe: {Path(recipe_path)}",
        f"Measurement geometry: {format_geometry(recipe.measurement_geometry.model_dump(mode='json'))}",
        f"Safety preset: {safety.name}",
        f"Gate1 instrument: {recipe.gate1_instrument.id} at {recipe.gate1_instrument.address}",
        f"Gate2 instrument: {recipe.gate2_instrument.id} at {recipe.gate2_instrument.address}",
        f"Gate1 NPLC: {recipe.gate1_instrument.nplc if recipe.gate1_instrument.nplc is not None else 'auto'}",
        f"Gate2 NPLC: {recipe.gate2_instrument.nplc if recipe.gate2_instrument.nplc is not None else 'auto'}",
        f"Lock-in: {recipe.lockin.id} at {recipe.lockin.address}",
        f"Lock-in channels: {', '.join(recipe.lockin.channels)}",
        f"Lock-in timing: {recipe.lockin.read_timing}",
        f"Gate1 sweep: {gate1_voltages[0]:.6g} V -> {gate1_voltages[-1]:.6g} V, {len(gate1_voltages)} points, settle {recipe.gate1_sweep.settle_s:.6g} s",
        f"Gate2 sweep: {gate2_voltages[0]:.6g} V -> {gate2_voltages[-1]:.6g} V, {len(gate2_voltages)} points, settle {recipe.gate2_sweep.settle_s:.6g} s",
        f"Total points: {len(gate1_voltages) * len(gate2_voltages)}",
        f"Gate1 compliance: {recipe.gate1_sweep.current_compliance_a:.6g} A",
        f"Gate2 compliance: {recipe.gate2_sweep.current_compliance_a:.6g} A",
        f"Safety current limit: {safety.max_abs_current_a:.6g} A",
    ]
    preview = max(0, preview_points)
    if preview:
        pairs = [(gate1_v, gate2_v) for gate1_v in gate1_voltages for gate2_v in gate2_voltages]
        head = pairs[:preview]
        tail = pairs[-preview:] if len(pairs) > preview else []
        lines.append("Preview points:")
        for index, (gate1_v, gate2_v) in enumerate(head):
            lines.append(f"  #{index}: Vg1={gate1_v:.6g} V, Vg2={gate2_v:.6g} V")
        if tail and tail[0] != head[0]:
            if len(pairs) > 2 * preview:
                lines.append("  ...")
            start_index = len(pairs) - len(tail)
            for offset, (gate1_v, gate2_v) in enumerate(tail):
                lines.append(f"  #{start_index + offset}: Vg1={gate1_v:.6g} V, Vg2={gate2_v:.6g} V")
    return "\n".join(lines)


def format_geometry(geometry: dict) -> str:
    method = geometry.get("method") or "two_terminal"
    terminal_count = geometry.get("terminal_count") or 2
    notes = geometry.get("notes")
    text = f"{method}, {terminal_count}-terminal"
    return f"{text}, {notes}" if notes else text


def run_dual_gate_lockin_sweep(
    recipe: DualGateLockInRecipe,
    safety: SafetyPreset,
    gate1_smu: SourceMeasureUnit,
    gate2_smu: SourceMeasureUnit,
    lockin: LockInAmplifier,
    recipe_path: str | Path | None = None,
    progress_callback: Callable[[DualGateLockInPoint, int], None] | None = None,
) -> dict[str, Any]:
    validate_dual_gate_lockin_recipe_against_safety(recipe, safety)
    writer = DualGateLockInRunWriter(Path(recipe.output.directory), recipe.measurement_name)
    writer.write_yaml_snapshot(writer.recipe_snapshot_path, recipe.model_dump(mode="json"))
    writer.write_yaml_snapshot(writer.safety_snapshot_path, safety.model_dump(mode="json"))
    points_written = 0
    metadata: dict[str, Any] = {
        "measurement_name": recipe.measurement_name,
        "measurement_type": "dual_gate_lockin_sweep",
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
        "gate1_instrument_probe": None,
        "gate2_instrument_probe": None,
        "lockin_probe": None,
        "csv_path": str(writer.csv_path),
        "metadata_path": str(writer.metadata_path),
        "recipe_snapshot_path": str(writer.recipe_snapshot_path),
        "safety_snapshot_path": str(writer.safety_snapshot_path),
    }

    try:
        gate1_smu.connect()
        gate2_smu.connect()
        lockin.connect()
        metadata["gate1_instrument_probe"] = gate1_smu.probe()
        metadata["gate2_instrument_probe"] = gate2_smu.probe()
        metadata["lockin_probe"] = lockin.probe()
        gate1_smu.configure_voltage_source(
            SMUVoltageSourceConfig(
                current_compliance_a=recipe.gate1_sweep.current_compliance_a,
                voltage_range_v=recipe.gate1_instrument.voltage_range_v,
                current_range_a=recipe.gate1_instrument.current_range_a,
                terminal=recipe.gate1_instrument.terminal,
                nplc=recipe.gate1_instrument.nplc,
            )
        )
        gate2_smu.configure_voltage_source(
            SMUVoltageSourceConfig(
                current_compliance_a=recipe.gate2_sweep.current_compliance_a,
                voltage_range_v=recipe.gate2_instrument.voltage_range_v,
                current_range_a=recipe.gate2_instrument.current_range_a,
                terminal=recipe.gate2_instrument.terminal,
                nplc=recipe.gate2_instrument.nplc,
            )
        )
        gate1_smu.output_on()
        gate2_smu.output_on()

        start = time.monotonic()
        gate1_voltages = gate_voltages_from_config(recipe.gate1_sweep)
        gate2_voltages = gate_voltages_from_config(recipe.gate2_sweep)
        total_points = len(gate1_voltages) * len(gate2_voltages)
        point_index = 0
        for gate1_index, gate1_voltage_v in enumerate(gate1_voltages):
            gate1_smu.set_voltage(float(gate1_voltage_v))
            if recipe.gate1_sweep.settle_s:
                time.sleep(recipe.gate1_sweep.settle_s)
            gate1_current_a, gate1_compliance_hit = gate1_smu.measure_current()
            if gate1_compliance_hit:
                raise SafetyLimitError("Gate1 instrument compliance was reached", "gate1_instrument_compliance")
            validate_point_current(gate1_current_a, safety)
            for gate2_index, gate2_voltage_v in enumerate(gate2_voltages):
                gate2_smu.set_voltage(float(gate2_voltage_v))
                if recipe.gate2_sweep.settle_s:
                    time.sleep(recipe.gate2_sweep.settle_s)
                gate2_current_a, gate2_compliance_hit = gate2_smu.measure_current()
                if gate2_compliance_hit:
                    raise SafetyLimitError("Gate2 instrument compliance was reached", "gate2_instrument_compliance")
                validate_point_current(gate2_current_a, safety)
                reading = lockin.read_channels()
                point = DualGateLockInPoint(
                    index=point_index,
                    gate1_index=gate1_index,
                    gate2_index=gate2_index,
                    gate1_voltage_v=float(gate1_voltage_v),
                    gate2_voltage_v=float(gate2_voltage_v),
                    gate1_current_a=float(gate1_current_a),
                    gate2_current_a=float(gate2_current_a),
                    elapsed_s=time.monotonic() - start,
                    gate1_compliance_hit=gate1_compliance_hit,
                    gate2_compliance_hit=gate2_compliance_hit,
                    lockin_x_v=reading.x_v,
                    lockin_y_v=reading.y_v,
                    lockin_r_v=reading.r_v,
                    lockin_theta_deg=reading.theta_deg,
                )
                writer.write_point(point)
                points_written += 1
                point_index += 1
                if progress_callback is not None:
                    progress_callback(point, total_points)

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
            gate1_smu.output_off()
        finally:
            try:
                gate2_smu.output_off()
            finally:
                gate1_smu.close()
                gate2_smu.close()
                lockin.close()
                metadata["finished_at"] = datetime.now().isoformat(timespec="seconds")
                metadata["points_written"] = points_written
                writer.write_metadata(metadata)
                writer.close()
