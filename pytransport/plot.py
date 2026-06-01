"""Small dependency-free SVG plots for measurement runs."""

from __future__ import annotations

from html import escape
from pathlib import Path

from .summary import read_points, summarize_run


def _scale(value: float, source_min: float, source_max: float, target_min: float, target_max: float) -> float:
    if source_max == source_min:
        return (target_min + target_max) / 2
    fraction = (value - source_min) / (source_max - source_min)
    return target_min + fraction * (target_max - target_min)


def write_iv_svg(run_dir: str | Path, output_path: str | Path | None = None) -> Path:
    run_path = Path(run_dir)
    points = read_points(run_path)
    if not points:
        raise ValueError(f"No points to plot in {run_path}")

    output = Path(output_path) if output_path is not None else run_path / "iv_plot.svg"
    summary = summarize_run(run_path)
    voltages = [point["voltage_v"] for point in points]
    currents = [point["current_a"] for point in points]
    v_min, v_max = min(voltages), max(voltages)
    i_min, i_max = min(currents), max(currents)
    if v_min == v_max:
        v_min -= 1
        v_max += 1
    if i_min == i_max:
        i_min -= 1
        i_max += 1

    width, height = 760, 560
    left, right, top, bottom = 92, 28, 92, 74
    plot_w = width - left - right
    plot_h = height - top - bottom

    polyline_points = []
    for point in points:
        x = _scale(point["voltage_v"], v_min, v_max, left, left + plot_w)
        y = _scale(point["current_a"], i_min, i_max, top + plot_h, top)
        polyline_points.append(f"{x:.2f},{y:.2f}")

    zero_x = _scale(0, v_min, v_max, left, left + plot_w) if v_min <= 0 <= v_max else None
    zero_y = _scale(0, i_min, i_max, top + plot_h, top) if i_min <= 0 <= i_max else None
    title = escape(run_path.name)
    resistance = (
        "n/a"
        if summary.fitted_resistance_ohm is None
        else f"{summary.fitted_resistance_ohm:.6g} ohm"
    )

    axis_lines = []
    if zero_x is not None:
        axis_lines.append(
            f'<line x1="{zero_x:.2f}" y1="{top}" x2="{zero_x:.2f}" y2="{top + plot_h}" '
            'stroke="#d1d5db" stroke-width="1" />'
        )
    if zero_y is not None:
        axis_lines.append(
            f'<line x1="{left}" y1="{zero_y:.2f}" x2="{left + plot_w}" y2="{zero_y:.2f}" '
            'stroke="#d1d5db" stroke-width="1" />'
        )

    circles = []
    for point in points:
        x = _scale(point["voltage_v"], v_min, v_max, left, left + plot_w)
        y = _scale(point["current_a"], i_min, i_max, top + plot_h, top)
        circles.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="3.2" fill="#0f766e" />')

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <rect width="100%" height="100%" fill="#ffffff" />
  <text x="{left}" y="30" font-family="Arial, sans-serif" font-size="18" fill="#111827">{title}</text>
  <text x="{left}" y="56" font-family="Arial, sans-serif" font-size="13" fill="#374151">completed={summary.completed}, points={summary.points}, fitted R={resistance}</text>
  <rect x="{left}" y="{top}" width="{plot_w}" height="{plot_h}" fill="#f9fafb" stroke="#9ca3af" stroke-width="1" />
  {''.join(axis_lines)}
  <polyline points="{' '.join(polyline_points)}" fill="none" stroke="#0f766e" stroke-width="2.2" />
  {''.join(circles)}
  <text x="{left + plot_w / 2 - 45:.2f}" y="{height - 22}" font-family="Arial, sans-serif" font-size="14" fill="#111827">Voltage (V)</text>
  <text x="18" y="{top + plot_h / 2 + 45:.2f}" transform="rotate(-90 18 {top + plot_h / 2 + 45:.2f})" font-family="Arial, sans-serif" font-size="14" fill="#111827">Current (A)</text>
  <text x="{left}" y="{height - 48}" font-family="Arial, sans-serif" font-size="12" fill="#4b5563">{v_min:.6g} V</text>
  <text x="{left + plot_w - 70}" y="{height - 48}" font-family="Arial, sans-serif" font-size="12" fill="#4b5563">{v_max:.6g} V</text>
  <text x="10" y="{top + 6}" font-family="Arial, sans-serif" font-size="12" fill="#4b5563">{i_max:.6g} A</text>
  <text x="10" y="{top + plot_h}" font-family="Arial, sans-serif" font-size="12" fill="#4b5563">{i_min:.6g} A</text>
</svg>
'''
    output.write_text(svg, encoding="utf-8")
    return output
