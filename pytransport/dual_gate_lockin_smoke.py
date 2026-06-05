"""Read-only dual-gate lock-in topology smoke acquisition."""

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
from .dual_gate_lockin import format_topology_settings
from .errors import SafetyLimitError
from .instruments.base import LockInAmplifier, SourceMeasureUnit
from .io import unique_run_dir
from .output_state import (
    all_outputs_off_after_run,
    any_output_enabled,
    initialize_output_state,
    output_off_with_state,
    output_on_with_state,
    zero_before_off_with_state,
)
from .recipes import DualGateLockInRecipe, SafetyPreset
from .safety import validate_dual_gate_lockin_recipe_against_safety, validate_point_current
from .smu_config import (
    build_voltage_source_config,
    compare_voltage_source_config_readback,
    raise_for_voltage_source_config_readback_mismatch,
    read_voltage_source_config_if_available,
    voltage_source_config_snapshot,
)


DUAL_GATE_LOCKIN_SMOKE_COLUMNS = [
    "sample_index",
    "elapsed_s",
    "lockin_x_v",
    "lockin_y_v",
    "lockin_r_v",
    "lockin_theta_deg",
]


DUAL_GATE_LOCKIN_ACTIVE_SMOKE_COLUMNS = [
    "sample_index",
    "elapsed_s",
    "gate1_voltage_v",
    "gate2_voltage_v",
    "gate1_current_a",
    "gate2_current_a",
    "gate1_compliance_hit",
    "gate2_compliance_hit",
    "lockin_x_v",
    "lockin_y_v",
    "lockin_r_v",
    "lockin_theta_deg",
]


@dataclass(frozen=True)
class DualGateLockInSmokePoint:
    sample_index: int
    elapsed_s: float
    lockin_x_v: float | None
    lockin_y_v: float | None
    lockin_r_v: float | None
    lockin_theta_deg: float | None

    def to_dict(self) -> dict[str, float | int | None]:
        return asdict(self)


@dataclass(frozen=True)
class DualGateLockInActiveSmokePoint:
    sample_index: int
    elapsed_s: float
    gate1_voltage_v: float
    gate2_voltage_v: float
    gate1_current_a: float
    gate2_current_a: float
    gate1_compliance_hit: bool
    gate2_compliance_hit: bool
    lockin_x_v: float | None
    lockin_y_v: float | None
    lockin_r_v: float | None
    lockin_theta_deg: float | None

    def to_dict(self) -> dict[str, float | int | bool | None]:
        return asdict(self)


class DualGateLockInSmokeWriter:
    def __init__(
        self,
        output_dir: Path,
        measurement_name: str,
        suffix: str = "readout_smoke",
        csv_name: str = "lockin_smoke.csv",
        columns: list[str] | None = None,
    ):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.run_dir = unique_run_dir(output_dir, f"{timestamp}_{safe_name(measurement_name)}_{safe_name(suffix)}")
        self.run_dir.mkdir(parents=True, exist_ok=False)
        self.csv_path = self.run_dir / csv_name
        self.metadata_path = self.run_dir / "metadata.json"
        self.recipe_snapshot_path = self.run_dir / "recipe_snapshot.yaml"
        self.safety_snapshot_path = self.run_dir / "safety_snapshot.yaml"
        self._csv_file = self.csv_path.open("w", newline="", encoding="utf-8")
        self._writer = csv.DictWriter(self._csv_file, fieldnames=columns or DUAL_GATE_LOCKIN_SMOKE_COLUMNS)
        self._writer.writeheader()
        self._csv_file.flush()

    def write_point(self, point: DualGateLockInSmokePoint) -> None:
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


def format_dual_gate_lockin_smoke_plan(
    recipe: DualGateLockInRecipe,
    safety: SafetyPreset,
    recipe_path: str | Path,
    samples: int,
    interval_s: float,
) -> str:
    return "\n".join(
        [
            f"Dual-Gate Lock-In Readout Smoke: {recipe.measurement_name}",
            f"Recipe: {Path(recipe_path)}",
            f"Safety preset: {safety.name}",
            "Gate outputs: not enabled",
            f"Gate1 instrument: {recipe.gate1_instrument.id} at {recipe.gate1_instrument.address}",
            f"Gate2 instrument: {recipe.gate2_instrument.id} at {recipe.gate2_instrument.address}",
            f"Lock-in: {recipe.lockin.id} at {recipe.lockin.address}",
            f"Samples: {samples}",
            f"Interval: {interval_s:.6g} s",
            *format_topology_settings(recipe.topology.model_dump(mode="json")),
        ]
    )


def format_dual_gate_lockin_active_smoke_plan(
    recipe: DualGateLockInRecipe,
    safety: SafetyPreset,
    recipe_path: str | Path,
    gate1_voltage_v: float,
    gate2_voltage_v: float,
    settle_s: float,
    samples: int,
    interval_s: float,
) -> str:
    return "\n".join(
        [
            f"Dual-Gate Lock-In Active-Gate Smoke: {recipe.measurement_name}",
            f"Recipe: {Path(recipe_path)}",
            f"Safety preset: {safety.name}",
            "Gate outputs: enabled only during this smoke test",
            f"Gate1 instrument: {recipe.gate1_instrument.id} at {recipe.gate1_instrument.address}",
            f"Gate2 instrument: {recipe.gate2_instrument.id} at {recipe.gate2_instrument.address}",
            f"Gate1 voltage: {gate1_voltage_v:.6g} V",
            f"Gate2 voltage: {gate2_voltage_v:.6g} V",
            f"Gate1 compliance: {recipe.gate1_sweep.current_compliance_a:.6g} A",
            f"Gate2 compliance: {recipe.gate2_sweep.current_compliance_a:.6g} A",
            f"Safety current limit: {safety.max_abs_current_a:.6g} A",
            f"Safety voltage limit: {safety.max_abs_voltage_v:.6g} V",
            f"Settle: {settle_s:.6g} s",
            f"Samples: {samples}",
            f"Interval: {interval_s:.6g} s",
            f"Lock-in: {recipe.lockin.id} at {recipe.lockin.address}",
            *format_topology_settings(recipe.topology.model_dump(mode="json")),
        ]
    )


def validate_active_gate_smoke_request(
    recipe: DualGateLockInRecipe,
    safety: SafetyPreset,
    gate1_voltage_v: float,
    gate2_voltage_v: float,
    samples: int,
    interval_s: float,
    settle_s: float,
) -> None:
    if samples < 1:
        raise ValueError("samples must be >= 1")
    if interval_s < 0:
        raise ValueError("interval_s must be >= 0")
    if settle_s < 0:
        raise ValueError("settle_s must be >= 0")
    validate_dual_gate_lockin_recipe_against_safety(recipe, safety)
    max_voltage = max(abs(gate1_voltage_v), abs(gate2_voltage_v))
    if max_voltage > safety.max_abs_voltage_v:
        raise SafetyLimitError(
            f"Active-gate smoke voltage {max_voltage:g} V exceeds safety limit {safety.max_abs_voltage_v:g} V",
            "active_gate_smoke_max_abs_voltage_v",
        )
    if recipe.gate1_instrument.voltage_range_v is not None and abs(gate1_voltage_v) > recipe.gate1_instrument.voltage_range_v:
        raise SafetyLimitError("Gate1 smoke voltage exceeds gate1 instrument voltage_range_v", "gate1_voltage_range_v")
    if recipe.gate2_instrument.voltage_range_v is not None and abs(gate2_voltage_v) > recipe.gate2_instrument.voltage_range_v:
        raise SafetyLimitError("Gate2 smoke voltage exceeds gate2 instrument voltage_range_v", "gate2_voltage_range_v")


def run_dual_gate_lockin_readout_smoke(
    recipe: DualGateLockInRecipe,
    safety: SafetyPreset,
    lockin: LockInAmplifier,
    samples: int,
    interval_s: float,
    recipe_path: str | Path | None = None,
    preflight_report: str | None = None,
    progress_callback: Callable[[DualGateLockInSmokePoint, int], None] | None = None,
) -> dict[str, Any]:
    if samples < 1:
        raise ValueError("samples must be >= 1")
    if interval_s < 0:
        raise ValueError("interval_s must be >= 0")
    validate_dual_gate_lockin_recipe_against_safety(recipe, safety)
    writer = DualGateLockInSmokeWriter(Path(recipe.output.directory), recipe.measurement_name)
    writer.write_yaml_snapshot(writer.recipe_snapshot_path, recipe.model_dump(mode="json"))
    writer.write_yaml_snapshot(writer.safety_snapshot_path, safety.model_dump(mode="json"))
    points_written = 0
    metadata: dict[str, Any] = {
        "measurement_name": recipe.measurement_name,
        "measurement_type": "dual_gate_lockin_readout_smoke",
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "completed": False,
        "interrupted": False,
        "error_type": None,
        "error_message": None,
        "points_written": 0,
        "samples_requested": samples,
        "interval_s": interval_s,
        "gate_outputs_enabled": False,
        "recipe": recipe.model_dump(mode="json"),
        "recipe_path": str(Path(recipe_path)) if recipe_path is not None else None,
        "safety": safety.model_dump(mode="json"),
        "topology": recipe.topology.model_dump(mode="json"),
        "preflight_report": preflight_report,
        "run_dir": str(writer.run_dir),
        "lockin_probe": None,
        "csv_path": str(writer.csv_path),
        "metadata_path": str(writer.metadata_path),
        "recipe_snapshot_path": str(writer.recipe_snapshot_path),
        "safety_snapshot_path": str(writer.safety_snapshot_path),
    }
    try:
        lockin.connect()
        metadata["lockin_probe"] = lockin.probe()
        start = time.monotonic()
        for sample_index in range(samples):
            if sample_index > 0 and interval_s:
                time.sleep(interval_s)
            reading = lockin.read_channels()
            point = DualGateLockInSmokePoint(
                sample_index=sample_index,
                elapsed_s=time.monotonic() - start,
                lockin_x_v=reading.x_v,
                lockin_y_v=reading.y_v,
                lockin_r_v=reading.r_v,
                lockin_theta_deg=reading.theta_deg,
            )
            writer.write_point(point)
            points_written += 1
            if progress_callback is not None:
                progress_callback(point, samples)
        metadata["completed"] = True
        return metadata
    except KeyboardInterrupt:
        metadata["interrupted"] = True
        metadata["error_type"] = "KeyboardInterrupt"
        metadata["error_message"] = "Readout smoke interrupted by user"
        return metadata
    except Exception as exc:
        metadata["error_type"] = type(exc).__name__
        metadata["error_message"] = str(exc)
        return metadata
    finally:
        try:
            lockin.close()
        finally:
            metadata["finished_at"] = datetime.now().isoformat(timespec="seconds")
            metadata["points_written"] = points_written
            writer.write_metadata(metadata)
            writer.close()


def run_dual_gate_lockin_active_gate_smoke(
    recipe: DualGateLockInRecipe,
    safety: SafetyPreset,
    gate1_smu: SourceMeasureUnit,
    gate2_smu: SourceMeasureUnit,
    lockin: LockInAmplifier,
    gate1_voltage_v: float,
    gate2_voltage_v: float,
    samples: int,
    interval_s: float,
    settle_s: float,
    recipe_path: str | Path | None = None,
    preflight_report: str | None = None,
    progress_callback: Callable[[DualGateLockInActiveSmokePoint, int], None] | None = None,
) -> dict[str, Any]:
    validate_active_gate_smoke_request(recipe, safety, gate1_voltage_v, gate2_voltage_v, samples, interval_s, settle_s)
    writer = DualGateLockInSmokeWriter(
        Path(recipe.output.directory),
        recipe.measurement_name,
        suffix="active_gate_smoke",
        csv_name="active_gate_smoke.csv",
        columns=DUAL_GATE_LOCKIN_ACTIVE_SMOKE_COLUMNS,
    )
    writer.write_yaml_snapshot(writer.recipe_snapshot_path, recipe.model_dump(mode="json"))
    writer.write_yaml_snapshot(writer.safety_snapshot_path, safety.model_dump(mode="json"))
    points_written = 0
    gate1_config = build_voltage_source_config(recipe.gate1_instrument, recipe.gate1_sweep.current_compliance_a)
    gate2_config = build_voltage_source_config(recipe.gate2_instrument, recipe.gate2_sweep.current_compliance_a)
    metadata: dict[str, Any] = {
        "measurement_name": recipe.measurement_name,
        "measurement_type": "dual_gate_lockin_active_gate_smoke",
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "completed": False,
        "interrupted": False,
        "error_type": None,
        "error_message": None,
        "triggered_limit": None,
        "points_written": 0,
        "samples_requested": samples,
        "interval_s": interval_s,
        "settle_s": settle_s,
        "gate1_voltage_v": gate1_voltage_v,
        "gate2_voltage_v": gate2_voltage_v,
        "gate_outputs_enabled": False,
        "outputs_off_after_run": False,
        "recipe": recipe.model_dump(mode="json"),
        "recipe_path": str(Path(recipe_path)) if recipe_path is not None else None,
        "safety": safety.model_dump(mode="json"),
        "topology": recipe.topology.model_dump(mode="json"),
        "preflight_report": preflight_report,
        "run_dir": str(writer.run_dir),
        "gate1_instrument_probe": None,
        "gate2_instrument_probe": None,
        "lockin_probe": None,
        "configured_gate1_smu": voltage_source_config_snapshot(gate1_config),
        "configured_gate2_smu": voltage_source_config_snapshot(gate2_config),
        "configured_gate1_smu_readback": None,
        "configured_gate2_smu_readback": None,
        "configured_gate1_smu_readback_check": None,
        "configured_gate2_smu_readback_check": None,
        "csv_path": str(writer.csv_path),
        "metadata_path": str(writer.metadata_path),
        "recipe_snapshot_path": str(writer.recipe_snapshot_path),
        "safety_snapshot_path": str(writer.safety_snapshot_path),
    }
    initialize_output_state(metadata, ["gate1", "gate2"])
    try:
        gate1_smu.connect()
        gate2_smu.connect()
        lockin.connect()
        metadata["gate1_instrument_probe"] = gate1_smu.probe()
        metadata["gate2_instrument_probe"] = gate2_smu.probe()
        metadata["lockin_probe"] = lockin.probe()
        gate1_smu.configure_voltage_source(gate1_config)
        gate2_smu.configure_voltage_source(gate2_config)
        metadata["configured_gate1_smu_readback"] = read_voltage_source_config_if_available(gate1_smu)
        metadata["configured_gate2_smu_readback"] = read_voltage_source_config_if_available(gate2_smu)
        metadata["configured_gate1_smu_readback_check"] = compare_voltage_source_config_readback(
            gate1_config, metadata["configured_gate1_smu_readback"]
        )
        metadata["configured_gate2_smu_readback_check"] = compare_voltage_source_config_readback(
            gate2_config, metadata["configured_gate2_smu_readback"]
        )
        raise_for_voltage_source_config_readback_mismatch("gate1", metadata["configured_gate1_smu_readback_check"])
        raise_for_voltage_source_config_readback_mismatch("gate2", metadata["configured_gate2_smu_readback_check"])
        gate1_smu.set_voltage(float(gate1_voltage_v))
        gate2_smu.set_voltage(float(gate2_voltage_v))
        output_on_with_state("gate1", gate1_smu, metadata)
        output_on_with_state("gate2", gate2_smu, metadata)
        metadata["gate_outputs_enabled"] = any_output_enabled(metadata)
        if settle_s:
            time.sleep(settle_s)
        start = time.monotonic()
        for sample_index in range(samples):
            if sample_index > 0 and interval_s:
                time.sleep(interval_s)
            gate1_current_a, gate1_compliance_hit = gate1_smu.measure_current()
            gate2_current_a, gate2_compliance_hit = gate2_smu.measure_current()
            if gate1_compliance_hit:
                raise SafetyLimitError("Gate1 instrument compliance was reached", "gate1_instrument_compliance")
            if gate2_compliance_hit:
                raise SafetyLimitError("Gate2 instrument compliance was reached", "gate2_instrument_compliance")
            validate_point_current(gate1_current_a, safety)
            validate_point_current(gate2_current_a, safety)
            reading = lockin.read_channels()
            point = DualGateLockInActiveSmokePoint(
                sample_index=sample_index,
                elapsed_s=time.monotonic() - start,
                gate1_voltage_v=float(gate1_voltage_v),
                gate2_voltage_v=float(gate2_voltage_v),
                gate1_current_a=float(gate1_current_a),
                gate2_current_a=float(gate2_current_a),
                gate1_compliance_hit=gate1_compliance_hit,
                gate2_compliance_hit=gate2_compliance_hit,
                lockin_x_v=reading.x_v,
                lockin_y_v=reading.y_v,
                lockin_r_v=reading.r_v,
                lockin_theta_deg=reading.theta_deg,
            )
            writer.write_point(point)
            points_written += 1
            if progress_callback is not None:
                progress_callback(point, samples)
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
        metadata["error_message"] = "Active-gate smoke interrupted by user"
        return metadata
    except Exception as exc:
        metadata["error_type"] = type(exc).__name__
        metadata["error_message"] = str(exc)
        return metadata
    finally:
        zero_before_off_with_state("gate1", gate1_smu, metadata)
        zero_before_off_with_state("gate2", gate2_smu, metadata)
        output_off_with_state("gate1", gate1_smu, metadata)
        output_off_with_state("gate2", gate2_smu, metadata)
        metadata["gate_outputs_enabled"] = any_output_enabled(metadata)
        metadata["outputs_off_after_run"] = all_outputs_off_after_run(metadata, ["gate1", "gate2"])
        try:
            gate1_smu.close()
        finally:
            try:
                gate2_smu.close()
            finally:
                lockin.close()
                metadata["finished_at"] = datetime.now().isoformat(timespec="seconds")
                metadata["points_written"] = points_written
                writer.write_metadata(metadata)
                writer.close()
