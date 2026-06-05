"""Review artifacts for AC / lock-in sweep runs."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Any

from .measurement_context import format_geometry
from .plot import _scale
from .report import fmt


@dataclass(frozen=True)
class AcLockInSummary:
    run_dir: Path
    completed: bool | None
    points: int
    bias_min_v: float | None
    bias_max_v: float | None
    source_current_min_a: float | None
    source_current_max_a: float | None
    lockin_r_min_v: float | None
    lockin_r_max_v: float | None
    lockin_theta_min_deg: float | None
    lockin_theta_max_deg: float | None
    error_type: str | None
    error_message: str | None


def read_ac_lockin_metadata(run_dir: str | Path) -> dict[str, Any]:
    metadata_path = Path(run_dir) / "metadata.json"
    if not metadata_path.exists():
        raise FileNotFoundError(f"Missing metadata: {metadata_path}")
    with metadata_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{metadata_path} must contain a JSON object")
    return data


def read_ac_lockin_points(run_dir: str | Path) -> list[dict[str, float | int | bool | None]]:
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
                    "bias_voltage_v": float(row["bias_voltage_v"]),
                    "source_current_a": float(row["source_current_a"]),
                    "elapsed_s": float(row["elapsed_s"]),
                    "source_resistance_ohm": parse_optional_float(row["source_resistance_ohm"]),
                    "source_compliance_hit": parse_bool(row["source_compliance_hit"]),
                    "lockin_x_v": parse_optional_float(row["lockin_x_v"]),
                    "lockin_y_v": parse_optional_float(row["lockin_y_v"]),
                    "lockin_r_v": parse_optional_float(row["lockin_r_v"]),
                    "lockin_theta_deg": parse_optional_float(row["lockin_theta_deg"]),
                }
            )
    return points


def parse_optional_float(value: str) -> float | None:
    if value == "" or value is None:
        return None
    return float(value)


def parse_bool(value: str) -> bool:
    return value.strip().lower() in {"true", "1", "yes"}


def summarize_ac_lockin_run(run_dir: str | Path) -> AcLockInSummary:
    path = Path(run_dir)
    metadata = read_ac_lockin_metadata(path)
    points = read_ac_lockin_points(path)
    biases = [float(point["bias_voltage_v"]) for point in points]
    currents = [float(point["source_current_a"]) for point in points]
    lockin_r = [point["lockin_r_v"] for point in points if point["lockin_r_v"] is not None]
    lockin_theta = [point["lockin_theta_deg"] for point in points if point["lockin_theta_deg"] is not None]
    return AcLockInSummary(
        run_dir=path,
        completed=metadata.get("completed"),
        points=len(points),
        bias_min_v=min(biases) if biases else None,
        bias_max_v=max(biases) if biases else None,
        source_current_min_a=min(currents) if currents else None,
        source_current_max_a=max(currents) if currents else None,
        lockin_r_min_v=min(lockin_r) if lockin_r else None,
        lockin_r_max_v=max(lockin_r) if lockin_r else None,
        lockin_theta_min_deg=min(lockin_theta) if lockin_theta else None,
        lockin_theta_max_deg=max(lockin_theta) if lockin_theta else None,
        error_type=metadata.get("error_type"),
        error_message=metadata.get("error_message"),
    )


def format_ac_lockin_summary(summary: AcLockInSummary) -> str:
    lines = [
        f"AC lock-in run: {summary.run_dir}",
        f"Completed: {summary.completed}",
        f"Points: {summary.points}",
        f"Bias range: {fmt(summary.bias_min_v, ' V')} to {fmt(summary.bias_max_v, ' V')}",
        f"Source current range: {fmt(summary.source_current_min_a, ' A')} to {fmt(summary.source_current_max_a, ' A')}",
        f"Lock-in R range: {fmt(summary.lockin_r_min_v, ' V')} to {fmt(summary.lockin_r_max_v, ' V')}",
        f"Lock-in theta range: {fmt(summary.lockin_theta_min_deg, ' deg')} to {fmt(summary.lockin_theta_max_deg, ' deg')}",
    ]
    if summary.error_type:
        lines.append(f"Error: {summary.error_type}: {summary.error_message}")
    return "\n".join(lines)


def write_ac_lockin_plot_svg(run_dir: str | Path, output_path: str | Path | None = None) -> Path:
    path = Path(run_dir)
    output = Path(output_path) if output_path is not None else path / "ac_lockin_plot.svg"
    points = read_ac_lockin_points(path)
    if not points:
        raise ValueError(f"No points to plot in {path}")
    xs = [float(point["bias_voltage_v"]) for point in points]
    ys = [float(point["lockin_r_v"] or 0.0) for point in points]
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
  <polyline points="{' '.join(polyline)}" fill="none" stroke="#0f766e" stroke-width="2.4" />
  <text x="{left + plot_w / 2 - 50:.2f}" y="{height - 24}" font-family="Arial, sans-serif" font-size="14" fill="#111827">Bias (V)</text>
  <text x="18" y="{top + plot_h / 2 + 48:.2f}" transform="rotate(-90 18 {top + plot_h / 2 + 48:.2f})" font-family="Arial, sans-serif" font-size="14" fill="#111827">Lock-in R (V)</text>
  <text x="{left}" y="{height - 48}" font-family="Arial, sans-serif" font-size="12" fill="#4b5563">{x_min:.6g} V</text>
  <text x="{left + plot_w - 70}" y="{height - 48}" font-family="Arial, sans-serif" font-size="12" fill="#4b5563">{x_max:.6g} V</text>
  <text x="10" y="{top + 6}" font-family="Arial, sans-serif" font-size="12" fill="#4b5563">{y_max:.6g} V</text>
  <text x="10" y="{top + plot_h}" font-family="Arial, sans-serif" font-size="12" fill="#4b5563">{y_min:.6g} V</text>
</svg>
'''
    output.write_text(svg, encoding="utf-8")
    return output


def write_ac_lockin_report(run_dir: str | Path, output_path: str | Path | None = None) -> Path:
    path = Path(run_dir)
    output = Path(output_path) if output_path is not None else path / "ac_lockin_report.md"
    output.write_text(format_ac_lockin_report(path), encoding="utf-8")
    return output


def format_ac_lockin_report(run_dir: str | Path) -> str:
    path = Path(run_dir)
    metadata = read_ac_lockin_metadata(path)
    summary = summarize_ac_lockin_run(path)
    recipe = metadata.get("recipe") or {}
    experiment = recipe.get("experiment") or {}
    measurement_geometry = recipe.get("measurement_geometry") or {}
    lockin = recipe.get("lockin") or {}
    source = recipe.get("source_instrument") or {}
    lines = [
        f"# {metadata.get('measurement_name') or path.name}",
        "",
        "## Summary",
        "",
        f"- Run directory: `{path}`",
        f"- Completed: {metadata.get('completed')}",
        f"- Points: {summary.points}",
        f"- Bias range: {fmt(summary.bias_min_v, ' V')} to {fmt(summary.bias_max_v, ' V')}",
        f"- Lock-in R range: {fmt(summary.lockin_r_min_v, ' V')} to {fmt(summary.lockin_r_max_v, ' V')}",
        f"- Lock-in theta range: {fmt(summary.lockin_theta_min_deg, ' deg')} to {fmt(summary.lockin_theta_max_deg, ' deg')}",
        "",
        "## Experiment",
        "",
        f"- Sample: {experiment.get('sample_id') or 'n/a'}",
        f"- Device: {experiment.get('device_id') or 'n/a'}",
        f"- Tags: {', '.join(experiment.get('tags') or []) or 'none'}",
        "",
        "## Instruments",
        "",
        f"- Measurement geometry: {format_geometry(measurement_geometry)}",
        f"- Lock-in input mode: {lockin.get('input_mode') or 'n/a'}",
        f"- Lock-in voltage input: {lockin.get('voltage_input') or 'n/a'}",
        f"- Source: {source.get('id') or 'n/a'} @ `{source.get('address') or 'n/a'}`",
        f"- Source NPLC: {source.get('nplc') if source.get('nplc') is not None else 'n/a'}",
        f"- Lock-in: {lockin.get('id') or 'n/a'} @ `{lockin.get('address') or 'n/a'}`",
        f"- Lock-in channels: {', '.join(lockin.get('channels') or []) or 'n/a'}",
        f"- Read timing: {lockin.get('read_timing') or 'n/a'}",
    ]
    if (path / "ac_lockin_plot.svg").exists():
        lines.extend(["", "## Plot", "", "![AC lock-in plot](ac_lockin_plot.svg)"])
    if metadata.get("error_type"):
        lines.extend(["", "## Error", "", f"- Type: {metadata.get('error_type')}", f"- Message: {metadata.get('error_message')}"])
    return "\n".join(lines) + "\n"
