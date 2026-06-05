"""Dual-gate Drain I-V sweep runner.

Current milestone: dry-run execution and artifact plumbing. Hardware execution
stays blocked at the CLI until a real wiring/smoke-test plan is verified.
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
from .instruments.base import SMUVoltageSourceConfig, SourceMeasureUnit
from .io import unique_run_dir
from .recipes import DualGateRecipe, SafetyPreset, gate_voltages_from_config, sweep_delays, sweep_voltages
from .safety import validate_dual_gate_recipe_against_safety, validate_point_current


DUAL_GATE_COLUMNS = [
    "index",
    "gate1_index",
    "gate2_index",
    "drain_index",
    "gate1_voltage_v",
    "gate2_voltage_v",
    "drain_voltage_v",
    "drain_current_a",
    "gate1_current_a",
    "gate2_current_a",
    "elapsed_s",
    "drain_resistance_ohm",
    "drain_compliance_hit",
    "gate1_compliance_hit",
    "gate2_compliance_hit",
]


@dataclass(frozen=True)
class DualGatePoint:
    index: int
    gate1_index: int
    gate2_index: int
    drain_index: int
    gate1_voltage_v: float
    gate2_voltage_v: float
    drain_voltage_v: float
    drain_current_a: float
    gate1_current_a: float
    gate2_current_a: float
    elapsed_s: float
    drain_resistance_ohm: float | None
    drain_compliance_hit: bool = False
    gate1_compliance_hit: bool = False
    gate2_compliance_hit: bool = False

    def to_dict(self) -> dict[str, float | int | bool | None]:
        return asdict(self)


class DualGateRunWriter:
    def __init__(self, output_dir: Path, measurement_name: str):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.run_dir = unique_run_dir(output_dir, f"{timestamp}_{safe_name(measurement_name)}")
        self.run_dir.mkdir(parents=True, exist_ok=False)
        self.csv_path = self.run_dir / "points.csv"
        self.metadata_path = self.run_dir / "metadata.json"
        self.recipe_snapshot_path = self.run_dir / "recipe_snapshot.yaml"
        self.safety_snapshot_path = self.run_dir / "safety_snapshot.yaml"
        self._csv_file = self.csv_path.open("w", newline="", encoding="utf-8")
        self._writer = csv.DictWriter(self._csv_file, fieldnames=DUAL_GATE_COLUMNS)
        self._writer.writeheader()
        self._csv_file.flush()

    def write_point(self, point: DualGatePoint) -> None:
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


def dual_gate_point_count(recipe: DualGateRecipe) -> int:
    return (
        len(gate_voltages_from_config(recipe.gate1_sweep))
        * len(gate_voltages_from_config(recipe.gate2_sweep))
        * len(sweep_voltages(recipe.drain_sweep))
    )


def format_dual_gate_plan(recipe: DualGateRecipe, safety: SafetyPreset, recipe_path: str | Path, preview_points: int = 3) -> str:
    gate1_voltages = gate_voltages_from_config(recipe.gate1_sweep)
    gate2_voltages = gate_voltages_from_config(recipe.gate2_sweep)
    drain_voltages = sweep_voltages(recipe.drain_sweep)
    total_points = len(gate1_voltages) * len(gate2_voltages) * len(drain_voltages)
    lines = [
        f"Dual-Gate Sweep Plan: {recipe.measurement_name}",
        f"Recipe: {Path(recipe_path)}",
        f"Measurement geometry: {format_geometry(recipe.measurement_geometry.model_dump(mode='json'))}",
        f"Safety preset: {safety.name}",
        f"Gate1 instrument: {recipe.gate1_instrument.id} at {recipe.gate1_instrument.address}",
        f"Gate2 instrument: {recipe.gate2_instrument.id} at {recipe.gate2_instrument.address}",
        f"Drain instrument: {recipe.drain_instrument.id} at {recipe.drain_instrument.address}",
        f"Gate1 NPLC: {recipe.gate1_instrument.nplc if recipe.gate1_instrument.nplc is not None else 'auto'}",
        f"Gate2 NPLC: {recipe.gate2_instrument.nplc if recipe.gate2_instrument.nplc is not None else 'auto'}",
        f"Drain NPLC: {recipe.drain_instrument.nplc if recipe.drain_instrument.nplc is not None else 'auto'}",
        f"Gate1 sweep: {gate1_voltages[0]:.6g} V -> {gate1_voltages[-1]:.6g} V, {len(gate1_voltages)} points, settle {recipe.gate1_sweep.settle_s:.6g} s",
        f"Gate2 sweep: {gate2_voltages[0]:.6g} V -> {gate2_voltages[-1]:.6g} V, {len(gate2_voltages)} points, settle {recipe.gate2_sweep.settle_s:.6g} s",
        f"Drain sweep: {drain_voltages[0]:.6g} V -> {drain_voltages[-1]:.6g} V, {len(drain_voltages)} points, mode {recipe.drain_sweep.mode}",
        f"Total points: {total_points}",
        f"Drain compliance: {recipe.drain_sweep.current_compliance_a:.6g} A",
        f"Gate1 compliance: {recipe.gate1_sweep.current_compliance_a:.6g} A",
        f"Gate2 compliance: {recipe.gate2_sweep.current_compliance_a:.6g} A",
    ]
    preview = max(0, preview_points)
    if preview:
        triples = [
            (gate1_v, gate2_v, drain_v)
            for gate1_v in gate1_voltages
            for gate2_v in gate2_voltages
            for drain_v in drain_voltages
        ]
        head = triples[:preview]
        tail = triples[-preview:] if len(triples) > preview else []
        lines.extend(["Preview points:"])
        for index, (gate1_v, gate2_v, drain_v) in enumerate(head):
            lines.append(f"  #{index}: Vg1={gate1_v:.6g} V, Vg2={gate2_v:.6g} V, Vd={drain_v:.6g} V")
        if tail and tail[0] != head[0]:
            if len(triples) > 2 * preview:
                lines.append("  ...")
            start_index = len(triples) - len(tail)
            for offset, (gate1_v, gate2_v, drain_v) in enumerate(tail):
                lines.append(f"  #{start_index + offset}: Vg1={gate1_v:.6g} V, Vg2={gate2_v:.6g} V, Vd={drain_v:.6g} V")
    return "\n".join(lines)


def format_geometry(geometry: dict) -> str:
    method = geometry.get("method") or "two_terminal"
    terminal_count = geometry.get("terminal_count") or 2
    notes = geometry.get("notes")
    text = f"{method}, {terminal_count}-terminal"
    return f"{text}, {notes}" if notes else text


def run_dual_gate_sweep(
    recipe: DualGateRecipe,
    safety: SafetyPreset,
    drain_smu: SourceMeasureUnit,
    gate1_smu: SourceMeasureUnit,
    gate2_smu: SourceMeasureUnit,
    recipe_path: str | Path | None = None,
    progress_callback: Callable[[DualGatePoint, int], None] | None = None,
) -> dict[str, Any]:
    validate_dual_gate_recipe_against_safety(recipe, safety)
    writer = DualGateRunWriter(Path(recipe.output.directory), recipe.measurement_name)
    writer.write_yaml_snapshot(writer.recipe_snapshot_path, recipe.model_dump(mode="json"))
    writer.write_yaml_snapshot(writer.safety_snapshot_path, safety.model_dump(mode="json"))
    points_written = 0
    metadata: dict[str, Any] = {
        "measurement_name": recipe.measurement_name,
        "measurement_type": "dual_gate_sweep",
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
        "gate1_instrument_probe": None,
        "gate2_instrument_probe": None,
        "csv_path": str(writer.csv_path),
        "metadata_path": str(writer.metadata_path),
        "recipe_snapshot_path": str(writer.recipe_snapshot_path),
        "safety_snapshot_path": str(writer.safety_snapshot_path),
    }

    try:
        drain_smu.connect()
        gate1_smu.connect()
        gate2_smu.connect()
        metadata["drain_instrument_probe"] = drain_smu.probe()
        metadata["gate1_instrument_probe"] = gate1_smu.probe()
        metadata["gate2_instrument_probe"] = gate2_smu.probe()
        drain_smu.configure_voltage_source(
            SMUVoltageSourceConfig(
                current_compliance_a=recipe.drain_sweep.current_compliance_a,
                voltage_range_v=recipe.drain_instrument.voltage_range_v,
                current_range_a=recipe.drain_instrument.current_range_a,
                terminal=recipe.drain_instrument.terminal,
                nplc=recipe.drain_instrument.nplc,
            )
        )
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
        drain_smu.output_on()

        start = time.monotonic()
        gate1_voltages = gate_voltages_from_config(recipe.gate1_sweep)
        gate2_voltages = gate_voltages_from_config(recipe.gate2_sweep)
        drain_voltages = sweep_voltages(recipe.drain_sweep)
        drain_delays = sweep_delays(recipe.drain_sweep)
        total_points = len(gate1_voltages) * len(gate2_voltages) * len(drain_voltages)
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
                for drain_index, (drain_voltage_v, delay_s) in enumerate(zip(drain_voltages, drain_delays)):
                    drain_smu.set_voltage(float(drain_voltage_v))
                    if delay_s:
                        time.sleep(delay_s)
                    drain_current_a, drain_compliance_hit = drain_smu.measure_current()
                    if drain_compliance_hit:
                        raise SafetyLimitError("Drain instrument compliance was reached", "drain_instrument_compliance")
                    validate_point_current(drain_current_a, safety)
                    drain_resistance_ohm = None if drain_current_a == 0 else float(drain_voltage_v) / drain_current_a
                    point = DualGatePoint(
                        index=point_index,
                        gate1_index=gate1_index,
                        gate2_index=gate2_index,
                        drain_index=drain_index,
                        gate1_voltage_v=float(gate1_voltage_v),
                        gate2_voltage_v=float(gate2_voltage_v),
                        drain_voltage_v=float(drain_voltage_v),
                        drain_current_a=float(drain_current_a),
                        gate1_current_a=float(gate1_current_a),
                        gate2_current_a=float(gate2_current_a),
                        elapsed_s=time.monotonic() - start,
                        drain_resistance_ohm=drain_resistance_ohm,
                        drain_compliance_hit=drain_compliance_hit,
                        gate1_compliance_hit=gate1_compliance_hit,
                        gate2_compliance_hit=gate2_compliance_hit,
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
        try:
            drain_smu.output_off()
        finally:
            try:
                gate1_smu.output_off()
            finally:
                try:
                    gate2_smu.output_off()
                finally:
                    drain_smu.close()
                    gate1_smu.close()
                    gate2_smu.close()
                    metadata["finished_at"] = datetime.now().isoformat(timespec="seconds")
                    metadata["points_written"] = points_written
                    writer.write_metadata(metadata)
                    writer.close()
