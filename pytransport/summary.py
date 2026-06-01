"""Summaries for completed or partial measurement runs."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RunSummary:
    run_dir: Path
    completed: bool | None
    points: int
    voltage_min_v: float | None
    voltage_max_v: float | None
    current_min_a: float | None
    current_max_a: float | None
    fitted_resistance_ohm: float | None
    error_type: str | None
    error_message: str | None


def _read_metadata(run_dir: Path) -> dict[str, Any]:
    metadata_path = run_dir / "metadata.json"
    if not metadata_path.exists():
        return {}
    with metadata_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{metadata_path} must contain a JSON object")
    return data


def read_points(run_dir: str | Path) -> list[dict[str, float]]:
    run_path = Path(run_dir)
    csv_path = run_path / "points.csv"
    if not csv_path.exists():
        raise FileNotFoundError(f"Missing points CSV: {csv_path}")
    points: list[dict[str, float]] = []
    with csv_path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            points.append(
                {
                    "voltage_v": float(row["voltage_v"]),
                    "current_a": float(row["current_a"]),
                }
            )
    return points


def fit_resistance_ohm(points: list[dict[str, float]]) -> float | None:
    if len(points) < 2:
        return None
    voltages = [point["voltage_v"] for point in points]
    currents = [point["current_a"] for point in points]
    current_mean = sum(currents) / len(currents)
    voltage_mean = sum(voltages) / len(voltages)
    denominator = sum((current - current_mean) ** 2 for current in currents)
    if denominator == 0:
        return None
    slope_v_per_a = sum(
        (current - current_mean) * (voltage - voltage_mean)
        for current, voltage in zip(currents, voltages)
    ) / denominator
    return slope_v_per_a


def summarize_run(run_dir: str | Path) -> RunSummary:
    path = Path(run_dir)
    metadata = _read_metadata(path)
    points = read_points(path)
    voltages = [point["voltage_v"] for point in points]
    currents = [point["current_a"] for point in points]
    return RunSummary(
        run_dir=path,
        completed=metadata.get("completed"),
        points=len(points),
        voltage_min_v=min(voltages) if voltages else None,
        voltage_max_v=max(voltages) if voltages else None,
        current_min_a=min(currents) if currents else None,
        current_max_a=max(currents) if currents else None,
        fitted_resistance_ohm=fit_resistance_ohm(points),
        error_type=metadata.get("error_type"),
        error_message=metadata.get("error_message"),
    )


def format_summary(summary: RunSummary) -> str:
    def fmt(value: float | None, unit: str = "") -> str:
        if value is None:
            return "n/a"
        return f"{value:.6g}{unit}"

    lines = [
        f"Run: {summary.run_dir}",
        f"Completed: {summary.completed}",
        f"Points: {summary.points}",
        f"Voltage range: {fmt(summary.voltage_min_v, ' V')} to {fmt(summary.voltage_max_v, ' V')}",
        f"Current range: {fmt(summary.current_min_a, ' A')} to {fmt(summary.current_max_a, ' A')}",
        f"Fitted resistance: {fmt(summary.fitted_resistance_ohm, ' ohm')}",
    ]
    if summary.error_type:
        lines.append(f"Error: {summary.error_type}: {summary.error_message}")
    return "\n".join(lines)
