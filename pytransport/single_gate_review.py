"""Review and export helpers for saved single-gate runs."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SingleGateSummary:
    run_dir: Path
    measurement_name: str
    completed: bool | None
    points: int
    gate_points: int
    drain_points: int
    gate_voltage_min_v: float | None
    gate_voltage_max_v: float | None
    drain_voltage_min_v: float | None
    drain_voltage_max_v: float | None
    drain_current_min_a: float | None
    drain_current_max_a: float | None
    gate_current_min_a: float | None
    gate_current_max_a: float | None
    gate_leakage_abs_max_a: float | None
    error_type: str | None
    error_message: str | None


def read_single_gate_metadata(run_dir: str | Path) -> dict[str, Any]:
    path = Path(run_dir) / "metadata.json"
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def read_single_gate_points(run_dir: str | Path) -> list[dict[str, float | int | bool]]:
    path = Path(run_dir) / "points.csv"
    if not path.exists():
        raise FileNotFoundError(f"Missing points CSV: {path}")
    rows: list[dict[str, float | int | bool]] = []
    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        required = {
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
        }
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{path} is not a single-gate points CSV; missing {sorted(missing)}")
        for row in reader:
            rows.append(
                {
                    "index": int(row["index"]),
                    "gate_index": int(row["gate_index"]),
                    "drain_index": int(row["drain_index"]),
                    "gate_voltage_v": float(row["gate_voltage_v"]),
                    "drain_voltage_v": float(row["drain_voltage_v"]),
                    "drain_current_a": float(row["drain_current_a"]),
                    "gate_current_a": float(row["gate_current_a"]),
                    "elapsed_s": float(row["elapsed_s"]),
                    "drain_resistance_ohm": parse_optional_float(row["drain_resistance_ohm"]),
                    "drain_compliance_hit": parse_bool(row["drain_compliance_hit"]),
                    "gate_compliance_hit": parse_bool(row["gate_compliance_hit"]),
                }
            )
    return rows


def parse_optional_float(value: str) -> float | None:
    if value in {"", "None", "none", "null"}:
        return None
    return float(value)


def parse_bool(value: str) -> bool:
    return value.strip().lower() in {"true", "1", "yes"}


def summarize_single_gate_run(run_dir: str | Path) -> SingleGateSummary:
    path = Path(run_dir)
    metadata = read_single_gate_metadata(path)
    points = read_single_gate_points(path)
    gate_voltages = [float(point["gate_voltage_v"]) for point in points]
    drain_voltages = [float(point["drain_voltage_v"]) for point in points]
    drain_currents = [float(point["drain_current_a"]) for point in points]
    gate_currents = [float(point["gate_current_a"]) for point in points]
    return SingleGateSummary(
        run_dir=path,
        measurement_name=metadata.get("measurement_name") or path.name,
        completed=metadata.get("completed"),
        points=len(points),
        gate_points=len({float(point["gate_voltage_v"]) for point in points}),
        drain_points=len({float(point["drain_voltage_v"]) for point in points}),
        gate_voltage_min_v=min(gate_voltages) if gate_voltages else None,
        gate_voltage_max_v=max(gate_voltages) if gate_voltages else None,
        drain_voltage_min_v=min(drain_voltages) if drain_voltages else None,
        drain_voltage_max_v=max(drain_voltages) if drain_voltages else None,
        drain_current_min_a=min(drain_currents) if drain_currents else None,
        drain_current_max_a=max(drain_currents) if drain_currents else None,
        gate_current_min_a=min(gate_currents) if gate_currents else None,
        gate_current_max_a=max(gate_currents) if gate_currents else None,
        gate_leakage_abs_max_a=max((abs(value) for value in gate_currents), default=None),
        error_type=metadata.get("error_type"),
        error_message=metadata.get("error_message"),
    )


def format_single_gate_summary(summary: SingleGateSummary) -> str:
    lines = [
        f"Single-gate run: {summary.run_dir}",
        f"Measurement: {summary.measurement_name}",
        f"Completed: {summary.completed}",
        f"Points: {summary.points}",
        f"Gate points: {summary.gate_points}",
        f"Drain points per gate: {summary.drain_points}",
        f"Gate voltage range: {fmt(summary.gate_voltage_min_v, ' V')} to {fmt(summary.gate_voltage_max_v, ' V')}",
        f"Drain voltage range: {fmt(summary.drain_voltage_min_v, ' V')} to {fmt(summary.drain_voltage_max_v, ' V')}",
        f"Drain current range: {fmt(summary.drain_current_min_a, ' A')} to {fmt(summary.drain_current_max_a, ' A')}",
        f"Gate current range: {fmt(summary.gate_current_min_a, ' A')} to {fmt(summary.gate_current_max_a, ' A')}",
        f"Max abs gate leakage: {fmt(summary.gate_leakage_abs_max_a, ' A')}",
    ]
    if summary.error_type:
        lines.append(f"Error: {summary.error_type}: {summary.error_message}")
    return "\n".join(lines)


def single_gate_stats_rows(run_dir: str | Path) -> list[dict[str, Any]]:
    points = read_single_gate_points(run_dir)
    rows = []
    gate_values = sorted({float(point["gate_voltage_v"]) for point in points})
    for gate_index, gate_voltage_v in enumerate(gate_values):
        group = [point for point in points if float(point["gate_voltage_v"]) == gate_voltage_v]
        drain_currents = [float(point["drain_current_a"]) for point in group]
        gate_currents = [float(point["gate_current_a"]) for point in group]
        rows.append(
            {
                "gate_index": gate_index,
                "gate_voltage_v": gate_voltage_v,
                "points": len(group),
                "drain_current_min_a": min(drain_currents) if drain_currents else None,
                "drain_current_max_a": max(drain_currents) if drain_currents else None,
                "gate_current_mean_a": mean(gate_currents),
                "gate_current_abs_max_a": max((abs(value) for value in gate_currents), default=None),
                "fitted_drain_resistance_ohm": fit_group_resistance(group),
            }
        )
    return rows


def write_single_gate_stats_csv(run_dir: str | Path, output_path: str | Path | None = None) -> Path:
    path = Path(run_dir)
    output = Path(output_path) if output_path is not None else path / "single_gate_stats.csv"
    fieldnames = [
        "gate_index",
        "gate_voltage_v",
        "points",
        "drain_current_min_a",
        "drain_current_max_a",
        "gate_current_mean_a",
        "gate_current_abs_max_a",
        "fitted_drain_resistance_ohm",
    ]
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in single_gate_stats_rows(path):
            writer.writerow(row)
    return output


def write_single_gate_heatmap_svg(run_dir: str | Path, output_path: str | Path | None = None) -> Path:
    path = Path(run_dir)
    points = read_single_gate_points(path)
    if not points:
        raise ValueError(f"No points to plot in {path}")
    output = Path(output_path) if output_path is not None else path / "single_gate_heatmap.svg"
    summary = summarize_single_gate_run(path)
    gate_values = sorted({float(point["gate_voltage_v"]) for point in points})
    drain_values = sorted({float(point["drain_voltage_v"]) for point in points})
    currents = [float(point["drain_current_a"]) for point in points]
    max_abs_current = max((abs(current) for current in currents), default=1.0) or 1.0
    by_coord = {
        (float(point["gate_voltage_v"]), float(point["drain_voltage_v"])): float(point["drain_current_a"])
        for point in points
    }

    width, height = 820, 560
    left, right, top, bottom = 104, 130, 82, 78
    plot_w = width - left - right
    plot_h = height - top - bottom
    cell_w = plot_w / max(1, len(drain_values))
    cell_h = plot_h / max(1, len(gate_values))
    cells = []
    for gate_pos, gate_voltage_v in enumerate(gate_values):
        y = top + (len(gate_values) - gate_pos - 1) * cell_h
        for drain_pos, drain_voltage_v in enumerate(drain_values):
            x = left + drain_pos * cell_w
            current = by_coord.get((gate_voltage_v, drain_voltage_v), 0.0)
            cells.append(
                f'<rect x="{x:.2f}" y="{y:.2f}" width="{cell_w + 0.2:.2f}" height="{cell_h + 0.2:.2f}" fill="{current_color(current, max_abs_current)}" />'
            )

    title = escape(summary.measurement_name)
    subtitle = (
        f"completed={summary.completed}, points={summary.points}, "
        f"gate leakage max={fmt(summary.gate_leakage_abs_max_a, ' A')}"
    )
    legend = legend_svg(left + plot_w + 28, top, plot_h)
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <rect width="100%" height="100%" fill="#ffffff" />
  <text x="{left}" y="30" font-family="Arial, sans-serif" font-size="18" fill="#111827">{title}</text>
  <text x="{left}" y="56" font-family="Arial, sans-serif" font-size="13" fill="#374151">{escape(subtitle)}</text>
  <rect x="{left}" y="{top}" width="{plot_w}" height="{plot_h}" fill="#f9fafb" stroke="#9ca3af" />
  {''.join(cells)}
  <rect x="{left}" y="{top}" width="{plot_w}" height="{plot_h}" fill="none" stroke="#374151" />
  {legend}
  <text x="{left + plot_w / 2 - 68:.2f}" y="{height - 22}" font-family="Arial, sans-serif" font-size="14" fill="#111827">Drain voltage (V)</text>
  <text x="20" y="{top + plot_h / 2 + 48:.2f}" transform="rotate(-90 20 {top + plot_h / 2 + 48:.2f})" font-family="Arial, sans-serif" font-size="14" fill="#111827">Gate voltage (V)</text>
  <text x="{left}" y="{height - 48}" font-family="Arial, sans-serif" font-size="12" fill="#4b5563">{drain_values[0]:.6g} V</text>
  <text x="{left + plot_w - 70}" y="{height - 48}" font-family="Arial, sans-serif" font-size="12" fill="#4b5563">{drain_values[-1]:.6g} V</text>
  <text x="36" y="{top + 6}" font-family="Arial, sans-serif" font-size="12" fill="#4b5563">{gate_values[-1]:.6g} V</text>
  <text x="36" y="{top + plot_h}" font-family="Arial, sans-serif" font-size="12" fill="#4b5563">{gate_values[0]:.6g} V</text>
  <text x="{left + plot_w + 58}" y="{top - 14}" font-family="Arial, sans-serif" font-size="12" fill="#111827">Id</text>
  <text x="{left + plot_w + 56}" y="{top + plot_h + 22}" font-family="Arial, sans-serif" font-size="11" fill="#4b5563">±{max_abs_current:.3g} A</text>
</svg>
'''
    output.write_text(svg, encoding="utf-8")
    return output


def write_single_gate_report(run_dir: str | Path, output_path: str | Path | None = None) -> Path:
    path = Path(run_dir)
    output = Path(output_path) if output_path is not None else path / "single_gate_report.md"
    output.write_text(format_single_gate_report(path), encoding="utf-8")
    return output


def format_single_gate_report(run_dir: str | Path) -> str:
    path = Path(run_dir)
    metadata = read_single_gate_metadata(path)
    recipe = metadata.get("recipe") or {}
    experiment = recipe.get("experiment") or {}
    summary = summarize_single_gate_run(path)
    stats_rows = single_gate_stats_rows(path)
    lines = [
        f"# {summary.measurement_name}",
        "",
        "## Summary",
        "",
        f"- Run directory: `{path}`",
        f"- Started: {metadata.get('started_at') or 'n/a'}",
        f"- Finished: {metadata.get('finished_at') or 'n/a'}",
        f"- Completed: {summary.completed}",
        f"- Points: {summary.points}",
        f"- Gate points: {summary.gate_points}",
        f"- Drain points per gate: {summary.drain_points}",
        f"- Gate voltage range: {fmt(summary.gate_voltage_min_v, ' V')} to {fmt(summary.gate_voltage_max_v, ' V')}",
        f"- Drain voltage range: {fmt(summary.drain_voltage_min_v, ' V')} to {fmt(summary.drain_voltage_max_v, ' V')}",
        f"- Drain current range: {fmt(summary.drain_current_min_a, ' A')} to {fmt(summary.drain_current_max_a, ' A')}",
        f"- Max abs gate leakage: {fmt(summary.gate_leakage_abs_max_a, ' A')}",
        "",
        "## Experiment",
        "",
        f"- Sample: {experiment.get('sample_id') or 'n/a'}",
        f"- Device: {experiment.get('device_id') or 'n/a'}",
        f"- Operator: {experiment.get('operator') or 'n/a'}",
        f"- Tags: {', '.join(experiment.get('tags') or []) or 'none'}",
        f"- Notes: {experiment.get('notes') or 'n/a'}",
        "",
        "## Gate Statistics",
        "",
        "| Gate V | Points | Drain I Min | Drain I Max | Gate I Mean | Gate I Abs Max | Fitted Drain R |",
        "|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in stats_rows:
        lines.append(
            (
                f"| {fmt(row['gate_voltage_v'], ' V')} | {row['points']} | "
                f"{fmt(row['drain_current_min_a'], ' A')} | {fmt(row['drain_current_max_a'], ' A')} | "
                f"{fmt(row['gate_current_mean_a'], ' A')} | {fmt(row['gate_current_abs_max_a'], ' A')} | "
                f"{fmt(row['fitted_drain_resistance_ohm'], ' ohm')} |"
            )
        )
    if (path / "single_gate_heatmap.svg").exists():
        lines.extend(["", "## Heatmap", "", "![Single-gate heatmap](single_gate_heatmap.svg)"])
    if summary.error_type:
        lines.extend(["", "## Error", "", f"- Type: {summary.error_type}", f"- Message: {summary.error_message}"])
    return "\n".join(lines) + "\n"


def fit_group_resistance(points: list[dict[str, Any]]) -> float | None:
    if len(points) < 2:
        return None
    currents = [float(point["drain_current_a"]) for point in points]
    voltages = [float(point["drain_voltage_v"]) for point in points]
    current_mean = mean(currents)
    voltage_mean = mean(voltages)
    if current_mean is None or voltage_mean is None:
        return None
    denominator = sum((current - current_mean) ** 2 for current in currents)
    if denominator == 0:
        return None
    return sum((current - current_mean) * (voltage - voltage_mean) for current, voltage in zip(currents, voltages)) / denominator


def mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def current_color(current: float, max_abs_current: float) -> str:
    fraction = max(-1.0, min(1.0, current / max_abs_current))
    if fraction >= 0:
        intensity = int(255 * fraction)
        return f"rgb({255 - intensity // 4},{245 - intensity // 2},{235 - intensity})"
    intensity = int(255 * abs(fraction))
    return f"rgb({235 - intensity},{245 - intensity // 2},{255 - intensity // 4})"


def legend_svg(x: float, y: float, height: float) -> str:
    steps = 24
    rects = []
    for index in range(steps):
        fraction = 1 - 2 * index / (steps - 1)
        rect_y = y + index * height / steps
        rects.append(
            f'<rect x="{x:.2f}" y="{rect_y:.2f}" width="24" height="{height / steps + 0.2:.2f}" fill="{current_color(fraction, 1.0)}" />'
        )
    return "".join(rects) + f'<rect x="{x:.2f}" y="{y:.2f}" width="24" height="{height:.2f}" fill="none" stroke="#6b7280" />'


def fmt(value: Any, unit: str = "") -> str:
    if value is None:
        return "n/a"
    if isinstance(value, int | float):
        return f"{value:.6g}{unit}"
    return f"{value}{unit}"
