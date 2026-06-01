"""Review artifacts for pulse measurement runs."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Any

from .plot import _scale
from .report import fmt


@dataclass(frozen=True)
class PulseSummary:
    run_dir: Path
    completed: bool | None
    points: int
    pulse_voltage_v: float | None
    width_s: float | None
    period_s: float | None
    duty_cycle: float | None
    current_min_a: float | None
    current_max_a: float | None
    error_type: str | None
    error_message: str | None


def read_pulse_metadata(run_dir: str | Path) -> dict[str, Any]:
    metadata_path = Path(run_dir) / "metadata.json"
    if not metadata_path.exists():
        raise FileNotFoundError(f"Missing metadata: {metadata_path}")
    with metadata_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{metadata_path} must contain a JSON object")
    return data


def read_pulse_points(run_dir: str | Path) -> list[dict[str, float | int | bool]]:
    csv_path = Path(run_dir) / "points.csv"
    if not csv_path.exists():
        raise FileNotFoundError(f"Missing points CSV: {csv_path}")
    points = []
    with csv_path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            points.append(
                {
                    "index": int(row["index"]),
                    "pulse_index": int(row["pulse_index"]),
                    "base_voltage_v": float(row["base_voltage_v"]),
                    "pulse_voltage_v": float(row["pulse_voltage_v"]),
                    "width_s": float(row["width_s"]),
                    "period_s": float(row["period_s"]),
                    "duty_cycle": float(row["duty_cycle"]),
                    "source_current_a": float(row["source_current_a"]),
                    "elapsed_s": float(row["elapsed_s"]),
                    "compliance_hit": row["compliance_hit"].strip().lower() in {"true", "1", "yes"},
                }
            )
    return points


def summarize_pulse_run(run_dir: str | Path) -> PulseSummary:
    path = Path(run_dir)
    metadata = read_pulse_metadata(path)
    points = read_pulse_points(path)
    currents = [float(point["source_current_a"]) for point in points]
    return PulseSummary(
        run_dir=path,
        completed=metadata.get("completed"),
        points=len(points),
        pulse_voltage_v=float(points[0]["pulse_voltage_v"]) if points else None,
        width_s=float(points[0]["width_s"]) if points else None,
        period_s=float(points[0]["period_s"]) if points else None,
        duty_cycle=float(points[0]["duty_cycle"]) if points else None,
        current_min_a=min(currents) if currents else None,
        current_max_a=max(currents) if currents else None,
        error_type=metadata.get("error_type"),
        error_message=metadata.get("error_message"),
    )


def format_pulse_summary(summary: PulseSummary) -> str:
    lines = [
        f"Pulse run: {summary.run_dir}",
        f"Completed: {summary.completed}",
        f"Points: {summary.points}",
        f"Pulse voltage: {fmt(summary.pulse_voltage_v, ' V')}",
        f"Width: {fmt(summary.width_s, ' s')}",
        f"Period: {fmt(summary.period_s, ' s')}",
        f"Duty cycle: {fmt(summary.duty_cycle)}",
        f"Current range: {fmt(summary.current_min_a, ' A')} to {fmt(summary.current_max_a, ' A')}",
    ]
    if summary.error_type:
        lines.append(f"Error: {summary.error_type}: {summary.error_message}")
    return "\n".join(lines)


def write_pulse_plot_svg(run_dir: str | Path, output_path: str | Path | None = None) -> Path:
    path = Path(run_dir)
    output = Path(output_path) if output_path is not None else path / "pulse_plot.svg"
    points = read_pulse_points(path)
    if not points:
        raise ValueError(f"No points to plot in {path}")
    xs = [float(point["pulse_index"]) for point in points]
    ys = [float(point["source_current_a"]) for point in points]
    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)
    if x_min == x_max:
        x_min -= 1
        x_max += 1
    if y_min == y_max:
        y_min -= 1
        y_max += 1
    width, height = 820, 520
    left, right, top, bottom = 86, 42, 64, 70
    plot_w = width - left - right
    plot_h = height - top - bottom
    polyline = []
    for x_value, y_value in zip(xs, ys):
        x = _scale(x_value, x_min, x_max, left, left + plot_w)
        y = _scale(y_value, y_min, y_max, top + plot_h, top)
        polyline.append(f"{x:.2f},{y:.2f}")
    title = escape(path.name)
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <rect width="100%" height="100%" fill="#ffffff" />
  <text x="{left}" y="34" font-family="Arial, sans-serif" font-size="18" fill="#111827">{title}</text>
  <rect x="{left}" y="{top}" width="{plot_w}" height="{plot_h}" fill="#f9fafb" stroke="#9ca3af" />
  <polyline points="{' '.join(polyline)}" fill="none" stroke="#7c3aed" stroke-width="2.4" />
  <text x="{left + plot_w / 2 - 50:.2f}" y="{height - 24}" font-family="Arial, sans-serif" font-size="14" fill="#111827">Pulse index</text>
  <text x="18" y="{top + plot_h / 2 + 48:.2f}" transform="rotate(-90 18 {top + plot_h / 2 + 48:.2f})" font-family="Arial, sans-serif" font-size="14" fill="#111827">Current (A)</text>
</svg>
'''
    output.write_text(svg, encoding="utf-8")
    return output


def write_pulse_report(run_dir: str | Path, output_path: str | Path | None = None) -> Path:
    path = Path(run_dir)
    output = Path(output_path) if output_path is not None else path / "pulse_report.md"
    summary = summarize_pulse_run(path)
    metadata = read_pulse_metadata(path)
    recipe = metadata.get("recipe") or {}
    source = recipe.get("source_instrument") or {}
    pulse = recipe.get("pulse") or {}
    lines = [
        f"# {metadata.get('measurement_name') or path.name}",
        "",
        "## Summary",
        "",
        f"- Run directory: `{path}`",
        f"- Completed: {metadata.get('completed')}",
        f"- Points: {summary.points}",
        f"- Pulse voltage: {fmt(summary.pulse_voltage_v, ' V')}",
        f"- Width: {fmt(summary.width_s, ' s')}",
        f"- Period: {fmt(summary.period_s, ' s')}",
        f"- Duty cycle: {fmt(summary.duty_cycle)}",
        f"- Current range: {fmt(summary.current_min_a, ' A')} to {fmt(summary.current_max_a, ' A')}",
        "",
        "## Recipe",
        "",
        f"- Source: {source.get('id') or 'n/a'} @ `{source.get('address') or 'n/a'}`",
        f"- Acquisition: {pulse.get('acquisition') or 'n/a'}",
    ]
    if (path / "pulse_plot.svg").exists():
        lines.extend(["", "## Plot", "", "![Pulse plot](pulse_plot.svg)"])
    if metadata.get("error_type"):
        lines.extend(["", "## Error", "", f"- Type: {metadata.get('error_type')}", f"- Message: {metadata.get('error_message')}"])
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output
