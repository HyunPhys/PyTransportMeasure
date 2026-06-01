"""CSV and JSON output helpers."""

from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from .model import MeasurementPoint


CSV_COLUMNS = [
    "index",
    "voltage_v",
    "current_a",
    "elapsed_s",
    "resistance_ohm",
    "compliance_hit",
]


class RunWriter:
    def __init__(self, output_dir: Path, measurement_name: str):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = measurement_name.replace(" ", "_")
        self.run_dir = unique_run_dir(output_dir, f"{timestamp}_{safe_name}")
        self.run_dir.mkdir(parents=True, exist_ok=False)
        self.csv_path = self.run_dir / "points.csv"
        self.metadata_path = self.run_dir / "metadata.json"
        self.recipe_snapshot_path = self.run_dir / "recipe_snapshot.yaml"
        self.safety_snapshot_path = self.run_dir / "safety_snapshot.yaml"
        self._csv_file = self.csv_path.open("w", newline="", encoding="utf-8")
        self._writer = csv.DictWriter(self._csv_file, fieldnames=CSV_COLUMNS)
        self._writer.writeheader()
        self._csv_file.flush()

    def write_point(self, point: MeasurementPoint) -> None:
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


def unique_run_dir(output_dir: Path, base_name: str) -> Path:
    candidate = output_dir / base_name
    if not candidate.exists():
        return candidate
    for suffix in range(2, 1000):
        candidate = output_dir / f"{base_name}_{suffix:02d}"
        if not candidate.exists():
            return candidate
    raise FileExistsError(f"Could not create a unique run directory for {base_name}")
