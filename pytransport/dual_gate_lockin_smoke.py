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
from .instruments.base import LockInAmplifier
from .io import unique_run_dir
from .recipes import DualGateLockInRecipe, SafetyPreset
from .safety import validate_dual_gate_lockin_recipe_against_safety


DUAL_GATE_LOCKIN_SMOKE_COLUMNS = [
    "sample_index",
    "elapsed_s",
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


class DualGateLockInSmokeWriter:
    def __init__(self, output_dir: Path, measurement_name: str):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.run_dir = unique_run_dir(output_dir, f"{timestamp}_{safe_name(measurement_name)}_readout_smoke")
        self.run_dir.mkdir(parents=True, exist_ok=False)
        self.csv_path = self.run_dir / "lockin_smoke.csv"
        self.metadata_path = self.run_dir / "metadata.json"
        self.recipe_snapshot_path = self.run_dir / "recipe_snapshot.yaml"
        self.safety_snapshot_path = self.run_dir / "safety_snapshot.yaml"
        self._csv_file = self.csv_path.open("w", newline="", encoding="utf-8")
        self._writer = csv.DictWriter(self._csv_file, fieldnames=DUAL_GATE_LOCKIN_SMOKE_COLUMNS)
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
