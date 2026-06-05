"""Single-gate Drain I-V sweep runner."""

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
from .instruments.base import SourceMeasureUnit
from .io import unique_run_dir
from .output_state import (
    command_voltage_with_state,
    initialize_output_state,
    output_off_with_state,
    output_on_with_state,
    zero_before_off_with_state,
)
from .recipes import SafetyPreset, SingleGateRecipe, gate_voltages_from_config, sweep_delays, sweep_voltages
from .safety import validate_point_current, validate_single_gate_recipe_against_safety
from .smu_config import (
    build_voltage_source_config,
    compare_voltage_source_config_readback,
    raise_for_voltage_source_config_readback_mismatch,
    read_voltage_source_config_if_available,
    voltage_source_config_snapshot,
)


SINGLE_GATE_COLUMNS = [
    "index",
    "gate_index",
    "drain_index",
    "gate_voltage_v",
    "drain_voltage_v",
    "drain_current_a",
    "gate_current_a",
    "elapsed_s",
    "drain_resistance_ohm",
    "drain_compliance_hit",
    "gate_compliance_hit",
]


@dataclass(frozen=True)
class SingleGatePoint:
    index: int
    gate_index: int
    drain_index: int
    gate_voltage_v: float
    drain_voltage_v: float
    drain_current_a: float
    gate_current_a: float
    elapsed_s: float
    drain_resistance_ohm: float | None
    drain_compliance_hit: bool = False
    gate_compliance_hit: bool = False

    def to_dict(self) -> dict[str, float | int | bool | None]:
        return asdict(self)


class SingleGateRunWriter:
    def __init__(self, output_dir: Path, measurement_name: str):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.run_dir = unique_run_dir(output_dir, f"{timestamp}_{safe_name(measurement_name)}")
        self.run_dir.mkdir(parents=True, exist_ok=False)
        self.csv_path = self.run_dir / "points.csv"
        self.metadata_path = self.run_dir / "metadata.json"
        self.recipe_snapshot_path = self.run_dir / "recipe_snapshot.yaml"
        self.safety_snapshot_path = self.run_dir / "safety_snapshot.yaml"
        self._csv_file = self.csv_path.open("w", newline="", encoding="utf-8")
        self._writer = csv.DictWriter(self._csv_file, fieldnames=SINGLE_GATE_COLUMNS)
        self._writer.writeheader()
        self._csv_file.flush()

    def write_point(self, point: SingleGatePoint) -> None:
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


def single_gate_point_count(recipe: SingleGateRecipe) -> int:
    return len(gate_voltages_from_config(recipe.gate_sweep)) * len(sweep_voltages(recipe.drain_sweep))


def format_single_gate_plan(recipe: SingleGateRecipe, safety: SafetyPreset, recipe_path: str | Path, preview_points: int = 3) -> str:
    gate_voltages = gate_voltages_from_config(recipe.gate_sweep)
    drain_voltages = sweep_voltages(recipe.drain_sweep)
    total_points = len(gate_voltages) * len(drain_voltages)
    lines = [
        f"Single-Gate Sweep Plan: {recipe.measurement_name}",
        f"Recipe: {Path(recipe_path)}",
        f"Measurement geometry: {format_geometry(recipe.measurement_geometry.model_dump(mode='json'))}",
        f"Safety preset: {safety.name}",
        f"Gate instrument: {recipe.gate_instrument.id} at {recipe.gate_instrument.address}",
        f"Drain instrument: {recipe.drain_instrument.id} at {recipe.drain_instrument.address}",
        f"Gate NPLC: {recipe.gate_instrument.nplc if recipe.gate_instrument.nplc is not None else 'auto'}",
        f"Drain NPLC: {recipe.drain_instrument.nplc if recipe.drain_instrument.nplc is not None else 'auto'}",
        f"Gate sweep: {gate_voltages[0]:.6g} V -> {gate_voltages[-1]:.6g} V, {len(gate_voltages)} points, settle {recipe.gate_sweep.settle_s:.6g} s",
        f"Drain sweep: {drain_voltages[0]:.6g} V -> {drain_voltages[-1]:.6g} V, {len(drain_voltages)} points, mode {recipe.drain_sweep.mode}",
        f"Total points: {total_points}",
        f"Drain compliance: {recipe.drain_sweep.current_compliance_a:.6g} A",
        f"Gate compliance: {recipe.gate_sweep.current_compliance_a:.6g} A",
    ]
    preview = max(0, preview_points)
    if preview:
        pairs = [(gate_v, drain_v) for gate_v in gate_voltages for drain_v in drain_voltages]
        head = pairs[:preview]
        tail = pairs[-preview:] if len(pairs) > preview else []
        lines.extend(["Preview points:"])
        for index, (gate_v, drain_v) in enumerate(head):
            lines.append(f"  #{index}: Vg={gate_v:.6g} V, Vd={drain_v:.6g} V")
        if tail and tail[0] != head[0]:
            if len(pairs) > 2 * preview:
                lines.append("  ...")
            start_index = len(pairs) - len(tail)
            for offset, (gate_v, drain_v) in enumerate(tail):
                lines.append(f"  #{start_index + offset}: Vg={gate_v:.6g} V, Vd={drain_v:.6g} V")
    return "\n".join(lines)


def format_geometry(geometry: dict) -> str:
    method = geometry.get("method") or "two_terminal"
    terminal_count = geometry.get("terminal_count") or 2
    notes = geometry.get("notes")
    text = f"{method}, {terminal_count}-terminal"
    return f"{text}, {notes}" if notes else text


def run_single_gate_sweep(
    recipe: SingleGateRecipe,
    safety: SafetyPreset,
    drain_smu: SourceMeasureUnit,
    gate_smu: SourceMeasureUnit,
    recipe_path: str | Path | None = None,
    progress_callback: Callable[[SingleGatePoint, int], None] | None = None,
) -> dict[str, Any]:
    validate_single_gate_recipe_against_safety(recipe, safety)
    writer = SingleGateRunWriter(Path(recipe.output.directory), recipe.measurement_name)
    writer.write_yaml_snapshot(writer.recipe_snapshot_path, recipe.model_dump(mode="json"))
    writer.write_yaml_snapshot(writer.safety_snapshot_path, safety.model_dump(mode="json"))
    points_written = 0
    drain_config = build_voltage_source_config(recipe.drain_instrument, recipe.drain_sweep.current_compliance_a)
    gate_config = build_voltage_source_config(recipe.gate_instrument, recipe.gate_sweep.current_compliance_a)
    metadata: dict[str, Any] = {
        "measurement_name": recipe.measurement_name,
        "measurement_type": "single_gate_sweep",
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
        "drain_instrument_probe": None,
        "gate_instrument_probe": None,
        "configured_drain_smu": voltage_source_config_snapshot(drain_config),
        "configured_gate_smu": voltage_source_config_snapshot(gate_config),
        "configured_drain_smu_readback": None,
        "configured_gate_smu_readback": None,
        "configured_drain_smu_readback_check": None,
        "configured_gate_smu_readback_check": None,
        "csv_path": str(writer.csv_path),
        "metadata_path": str(writer.metadata_path),
        "recipe_snapshot_path": str(writer.recipe_snapshot_path),
        "safety_snapshot_path": str(writer.safety_snapshot_path),
    }
    initialize_output_state(metadata, ["drain", "gate"])

    try:
        drain_smu.connect()
        gate_smu.connect()
        metadata["drain_instrument_probe"] = drain_smu.probe()
        metadata["gate_instrument_probe"] = gate_smu.probe()
        drain_smu.configure_voltage_source(drain_config)
        gate_smu.configure_voltage_source(gate_config)
        metadata["configured_drain_smu_readback"] = read_voltage_source_config_if_available(drain_smu)
        metadata["configured_gate_smu_readback"] = read_voltage_source_config_if_available(gate_smu)
        metadata["configured_drain_smu_readback_check"] = compare_voltage_source_config_readback(
            drain_config, metadata["configured_drain_smu_readback"]
        )
        metadata["configured_gate_smu_readback_check"] = compare_voltage_source_config_readback(
            gate_config, metadata["configured_gate_smu_readback"]
        )
        raise_for_voltage_source_config_readback_mismatch("drain", metadata["configured_drain_smu_readback_check"])
        raise_for_voltage_source_config_readback_mismatch("gate", metadata["configured_gate_smu_readback_check"])
        output_on_with_state("gate", gate_smu, metadata)
        output_on_with_state("drain", drain_smu, metadata)

        start = time.monotonic()
        gate_voltages = gate_voltages_from_config(recipe.gate_sweep)
        drain_voltages = sweep_voltages(recipe.drain_sweep)
        drain_delays = sweep_delays(recipe.drain_sweep)
        total_points = len(gate_voltages) * len(drain_voltages)
        point_index = 0
        for gate_index, gate_voltage_v in enumerate(gate_voltages):
            command_voltage_with_state("gate", gate_smu, metadata, float(gate_voltage_v))
            if recipe.gate_sweep.settle_s:
                time.sleep(recipe.gate_sweep.settle_s)
            gate_current_a, gate_compliance_hit = gate_smu.measure_current()
            if gate_compliance_hit:
                raise SafetyLimitError("Gate instrument compliance was reached", "gate_instrument_compliance")
            validate_point_current(gate_current_a, safety)
            for drain_index, (drain_voltage_v, delay_s) in enumerate(zip(drain_voltages, drain_delays)):
                command_voltage_with_state("drain", drain_smu, metadata, float(drain_voltage_v))
                if delay_s:
                    time.sleep(delay_s)
                drain_current_a, drain_compliance_hit = drain_smu.measure_current()
                if drain_compliance_hit:
                    raise SafetyLimitError("Drain instrument compliance was reached", "drain_instrument_compliance")
                validate_point_current(drain_current_a, safety)
                drain_resistance_ohm = None if drain_current_a == 0 else float(drain_voltage_v) / drain_current_a
                point = SingleGatePoint(
                    index=point_index,
                    gate_index=gate_index,
                    drain_index=drain_index,
                    gate_voltage_v=float(gate_voltage_v),
                    drain_voltage_v=float(drain_voltage_v),
                    drain_current_a=float(drain_current_a),
                    gate_current_a=float(gate_current_a),
                    elapsed_s=time.monotonic() - start,
                    drain_resistance_ohm=drain_resistance_ohm,
                    drain_compliance_hit=drain_compliance_hit,
                    gate_compliance_hit=gate_compliance_hit,
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
    except KeyboardInterrupt as exc:
        metadata["interrupted"] = True
        metadata["error_type"] = type(exc).__name__
        metadata["error_message"] = "Measurement interrupted by user"
        return metadata
    except Exception as exc:
        metadata["error_type"] = type(exc).__name__
        metadata["error_message"] = str(exc)
        return metadata
    finally:
        zero_before_off_with_state("drain", drain_smu, metadata)
        zero_before_off_with_state("gate", gate_smu, metadata)
        output_off_with_state("drain", drain_smu, metadata)
        output_off_with_state("gate", gate_smu, metadata)
        drain_smu.close()
        gate_smu.close()
        metadata["finished_at"] = datetime.now().isoformat(timespec="seconds")
        metadata["points_written"] = points_written
        writer.write_metadata(metadata)
        writer.close()
