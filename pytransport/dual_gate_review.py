"""Review and export helpers for saved dual-gate runs."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Any

from .single_gate_review import current_color, fit_group_resistance, fmt, legend_svg, mean, parse_bool, parse_optional_float


@dataclass(frozen=True)
class DualGateSummary:
    run_dir: Path
    measurement_name: str
    completed: bool | None
    points: int
    gate1_points: int
    gate2_points: int
    drain_points: int
    gate1_voltage_min_v: float | None
    gate1_voltage_max_v: float | None
    gate2_voltage_min_v: float | None
    gate2_voltage_max_v: float | None
    drain_voltage_min_v: float | None
    drain_voltage_max_v: float | None
    drain_current_min_a: float | None
    drain_current_max_a: float | None
    gate1_leakage_abs_max_a: float | None
    gate2_leakage_abs_max_a: float | None
    error_type: str | None
    error_message: str | None


def read_dual_gate_metadata(run_dir: str | Path) -> dict[str, Any]:
    path = Path(run_dir) / "metadata.json"
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def read_dual_gate_points(run_dir: str | Path) -> list[dict[str, float | int | bool]]:
    path = Path(run_dir) / "points.csv"
    if not path.exists():
        raise FileNotFoundError(f"Missing points CSV: {path}")
    rows: list[dict[str, float | int | bool]] = []
    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        required = {
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
        }
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{path} is not a dual-gate points CSV; missing {sorted(missing)}")
        for row in reader:
            rows.append(
                {
                    "index": int(row["index"]),
                    "gate1_index": int(row["gate1_index"]),
                    "gate2_index": int(row["gate2_index"]),
                    "drain_index": int(row["drain_index"]),
                    "gate1_voltage_v": float(row["gate1_voltage_v"]),
                    "gate2_voltage_v": float(row["gate2_voltage_v"]),
                    "drain_voltage_v": float(row["drain_voltage_v"]),
                    "drain_current_a": float(row["drain_current_a"]),
                    "gate1_current_a": float(row["gate1_current_a"]),
                    "gate2_current_a": float(row["gate2_current_a"]),
                    "elapsed_s": float(row["elapsed_s"]),
                    "drain_resistance_ohm": parse_optional_float(row["drain_resistance_ohm"]),
                    "drain_compliance_hit": parse_bool(row["drain_compliance_hit"]),
                    "gate1_compliance_hit": parse_bool(row["gate1_compliance_hit"]),
                    "gate2_compliance_hit": parse_bool(row["gate2_compliance_hit"]),
                }
            )
    return rows


def summarize_dual_gate_run(run_dir: str | Path) -> DualGateSummary:
    path = Path(run_dir)
    metadata = read_dual_gate_metadata(path)
    points = read_dual_gate_points(path)
    gate1_voltages = [float(point["gate1_voltage_v"]) for point in points]
    gate2_voltages = [float(point["gate2_voltage_v"]) for point in points]
    drain_voltages = [float(point["drain_voltage_v"]) for point in points]
    drain_currents = [float(point["drain_current_a"]) for point in points]
    gate1_currents = [float(point["gate1_current_a"]) for point in points]
    gate2_currents = [float(point["gate2_current_a"]) for point in points]
    return DualGateSummary(
        run_dir=path,
        measurement_name=metadata.get("measurement_name") or path.name,
        completed=metadata.get("completed"),
        points=len(points),
        gate1_points=len({float(point["gate1_voltage_v"]) for point in points}),
        gate2_points=len({float(point["gate2_voltage_v"]) for point in points}),
        drain_points=len({float(point["drain_voltage_v"]) for point in points}),
        gate1_voltage_min_v=min(gate1_voltages) if gate1_voltages else None,
        gate1_voltage_max_v=max(gate1_voltages) if gate1_voltages else None,
        gate2_voltage_min_v=min(gate2_voltages) if gate2_voltages else None,
        gate2_voltage_max_v=max(gate2_voltages) if gate2_voltages else None,
        drain_voltage_min_v=min(drain_voltages) if drain_voltages else None,
        drain_voltage_max_v=max(drain_voltages) if drain_voltages else None,
        drain_current_min_a=min(drain_currents) if drain_currents else None,
        drain_current_max_a=max(drain_currents) if drain_currents else None,
        gate1_leakage_abs_max_a=max((abs(value) for value in gate1_currents), default=None),
        gate2_leakage_abs_max_a=max((abs(value) for value in gate2_currents), default=None),
        error_type=metadata.get("error_type"),
        error_message=metadata.get("error_message"),
    )


def format_dual_gate_summary(summary: DualGateSummary) -> str:
    lines = [
        f"Dual-gate run: {summary.run_dir}",
        f"Measurement: {summary.measurement_name}",
        f"Completed: {summary.completed}",
        f"Points: {summary.points}",
        f"Gate1 points: {summary.gate1_points}",
        f"Gate2 points: {summary.gate2_points}",
        f"Drain points per gate pair: {summary.drain_points}",
        f"Gate1 voltage range: {fmt(summary.gate1_voltage_min_v, ' V')} to {fmt(summary.gate1_voltage_max_v, ' V')}",
        f"Gate2 voltage range: {fmt(summary.gate2_voltage_min_v, ' V')} to {fmt(summary.gate2_voltage_max_v, ' V')}",
        f"Drain voltage range: {fmt(summary.drain_voltage_min_v, ' V')} to {fmt(summary.drain_voltage_max_v, ' V')}",
        f"Drain current range: {fmt(summary.drain_current_min_a, ' A')} to {fmt(summary.drain_current_max_a, ' A')}",
        f"Max abs gate1 leakage: {fmt(summary.gate1_leakage_abs_max_a, ' A')}",
        f"Max abs gate2 leakage: {fmt(summary.gate2_leakage_abs_max_a, ' A')}",
    ]
    if summary.error_type:
        lines.append(f"Error: {summary.error_type}: {summary.error_message}")
    return "\n".join(lines)


def dual_gate_stats_rows(run_dir: str | Path) -> list[dict[str, Any]]:
    points = read_dual_gate_points(run_dir)
    rows = []
    gate_pairs = sorted({(float(point["gate1_voltage_v"]), float(point["gate2_voltage_v"])) for point in points})
    for index, (gate1_voltage_v, gate2_voltage_v) in enumerate(gate_pairs):
        group = [
            point
            for point in points
            if float(point["gate1_voltage_v"]) == gate1_voltage_v and float(point["gate2_voltage_v"]) == gate2_voltage_v
        ]
        drain_currents = [float(point["drain_current_a"]) for point in group]
        gate1_currents = [float(point["gate1_current_a"]) for point in group]
        gate2_currents = [float(point["gate2_current_a"]) for point in group]
        rows.append(
            {
                "gate_pair_index": index,
                "gate1_voltage_v": gate1_voltage_v,
                "gate2_voltage_v": gate2_voltage_v,
                "points": len(group),
                "drain_current_mean_a": mean(drain_currents),
                "drain_current_min_a": min(drain_currents) if drain_currents else None,
                "drain_current_max_a": max(drain_currents) if drain_currents else None,
                "gate1_current_abs_max_a": max((abs(value) for value in gate1_currents), default=None),
                "gate2_current_abs_max_a": max((abs(value) for value in gate2_currents), default=None),
                "fitted_drain_resistance_ohm": fit_group_resistance(group),
            }
        )
    return rows


def write_dual_gate_stats_csv(run_dir: str | Path, output_path: str | Path | None = None) -> Path:
    path = Path(run_dir)
    output = Path(output_path) if output_path is not None else path / "dual_gate_stats.csv"
    fieldnames = [
        "gate_pair_index",
        "gate1_voltage_v",
        "gate2_voltage_v",
        "points",
        "drain_current_mean_a",
        "drain_current_min_a",
        "drain_current_max_a",
        "gate1_current_abs_max_a",
        "gate2_current_abs_max_a",
        "fitted_drain_resistance_ohm",
    ]
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in dual_gate_stats_rows(path):
            writer.writerow(row)
    return output


def write_dual_gate_heatmap_svg(run_dir: str | Path, output_path: str | Path | None = None) -> Path:
    path = Path(run_dir)
    rows = dual_gate_stats_rows(path)
    if not rows:
        raise ValueError(f"No points to plot in {path}")
    output = Path(output_path) if output_path is not None else path / "dual_gate_heatmap.svg"
    summary = summarize_dual_gate_run(path)
    gate1_values = sorted({float(row["gate1_voltage_v"]) for row in rows})
    gate2_values = sorted({float(row["gate2_voltage_v"]) for row in rows})
    currents = [float(row["drain_current_mean_a"]) for row in rows if row["drain_current_mean_a"] is not None]
    max_abs_current = max((abs(current) for current in currents), default=1.0) or 1.0
    by_coord = {
        (float(row["gate1_voltage_v"]), float(row["gate2_voltage_v"])): float(row["drain_current_mean_a"] or 0.0)
        for row in rows
    }

    width, height = 820, 560
    left, right, top, bottom = 104, 130, 82, 78
    plot_w = width - left - right
    plot_h = height - top - bottom
    cell_w = plot_w / max(1, len(gate2_values))
    cell_h = plot_h / max(1, len(gate1_values))
    cells = []
    for gate1_pos, gate1_voltage_v in enumerate(gate1_values):
        y = top + (len(gate1_values) - gate1_pos - 1) * cell_h
        for gate2_pos, gate2_voltage_v in enumerate(gate2_values):
            x = left + gate2_pos * cell_w
            current = by_coord.get((gate1_voltage_v, gate2_voltage_v), 0.0)
            cells.append(
                f'<rect x="{x:.2f}" y="{y:.2f}" width="{cell_w + 0.2:.2f}" height="{cell_h + 0.2:.2f}" fill="{current_color(current, max_abs_current)}" />'
            )

    title = escape(summary.measurement_name)
    subtitle = (
        f"completed={summary.completed}, points={summary.points}, "
        f"gate1 leakage max={fmt(summary.gate1_leakage_abs_max_a, ' A')}, "
        f"gate2 leakage max={fmt(summary.gate2_leakage_abs_max_a, ' A')}"
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
  <text x="{left + plot_w / 2 - 42:.2f}" y="{height - 22}" font-family="Arial, sans-serif" font-size="14" fill="#111827">Gate2 voltage (V)</text>
  <text x="20" y="{top + plot_h / 2 + 42:.2f}" transform="rotate(-90 20 {top + plot_h / 2 + 42:.2f})" font-family="Arial, sans-serif" font-size="14" fill="#111827">Gate1 voltage (V)</text>
  <text x="{left}" y="{height - 48}" font-family="Arial, sans-serif" font-size="12" fill="#4b5563">{gate2_values[0]:.6g} V</text>
  <text x="{left + plot_w - 70}" y="{height - 48}" font-family="Arial, sans-serif" font-size="12" fill="#4b5563">{gate2_values[-1]:.6g} V</text>
  <text x="36" y="{top + 6}" font-family="Arial, sans-serif" font-size="12" fill="#4b5563">{gate1_values[-1]:.6g} V</text>
  <text x="36" y="{top + plot_h}" font-family="Arial, sans-serif" font-size="12" fill="#4b5563">{gate1_values[0]:.6g} V</text>
  <text x="{left + plot_w + 58}" y="{top - 14}" font-family="Arial, sans-serif" font-size="12" fill="#111827">mean Id</text>
  <text x="{left + plot_w + 56}" y="{top + plot_h + 22}" font-family="Arial, sans-serif" font-size="11" fill="#4b5563">+/-{max_abs_current:.3g} A</text>
</svg>
'''
    output.write_text(svg, encoding="utf-8")
    return output


def write_dual_gate_report(run_dir: str | Path, output_path: str | Path | None = None) -> Path:
    path = Path(run_dir)
    output = Path(output_path) if output_path is not None else path / "dual_gate_report.md"
    output.write_text(format_dual_gate_report(path), encoding="utf-8")
    return output


def format_dual_gate_report(run_dir: str | Path) -> str:
    path = Path(run_dir)
    metadata = read_dual_gate_metadata(path)
    recipe = metadata.get("recipe") or {}
    experiment = recipe.get("experiment") or {}
    summary = summarize_dual_gate_run(path)
    stats_rows = dual_gate_stats_rows(path)
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
        f"- Gate1 points: {summary.gate1_points}",
        f"- Gate2 points: {summary.gate2_points}",
        f"- Drain points per gate pair: {summary.drain_points}",
        f"- Gate1 voltage range: {fmt(summary.gate1_voltage_min_v, ' V')} to {fmt(summary.gate1_voltage_max_v, ' V')}",
        f"- Gate2 voltage range: {fmt(summary.gate2_voltage_min_v, ' V')} to {fmt(summary.gate2_voltage_max_v, ' V')}",
        f"- Drain current range: {fmt(summary.drain_current_min_a, ' A')} to {fmt(summary.drain_current_max_a, ' A')}",
        f"- Max abs gate1 leakage: {fmt(summary.gate1_leakage_abs_max_a, ' A')}",
        f"- Max abs gate2 leakage: {fmt(summary.gate2_leakage_abs_max_a, ' A')}",
        "",
        "## Experiment",
        "",
        f"- Sample: {experiment.get('sample_id') or 'n/a'}",
        f"- Device: {experiment.get('device_id') or 'n/a'}",
        f"- Operator: {experiment.get('operator') or 'n/a'}",
        f"- Tags: {', '.join(experiment.get('tags') or []) or 'none'}",
        f"- Notes: {experiment.get('notes') or 'n/a'}",
        "",
        "## Gate-Pair Statistics",
        "",
        "| Gate1 V | Gate2 V | Points | Mean Drain I | Gate1 I Abs Max | Gate2 I Abs Max | Fitted Drain R |",
        "|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in stats_rows:
        lines.append(
            (
                f"| {fmt(row['gate1_voltage_v'], ' V')} | {fmt(row['gate2_voltage_v'], ' V')} | {row['points']} | "
                f"{fmt(row['drain_current_mean_a'], ' A')} | {fmt(row['gate1_current_abs_max_a'], ' A')} | "
                f"{fmt(row['gate2_current_abs_max_a'], ' A')} | {fmt(row['fitted_drain_resistance_ohm'], ' ohm')} |"
            )
        )
    if (path / "dual_gate_heatmap.svg").exists():
        lines.extend(["", "## Heatmap", "", "![Dual-gate heatmap](dual_gate_heatmap.svg)"])
    if summary.error_type:
        lines.extend(["", "## Error", "", f"- Type: {summary.error_type}", f"- Message: {summary.error_message}"])
    return "\n".join(lines) + "\n"
