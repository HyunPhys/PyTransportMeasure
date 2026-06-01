"""Review artifacts for completed batch/session runs."""

from __future__ import annotations

import json
import csv
from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Any

from .plot import _scale
from .report import fmt
from .summary import RunSummary, read_points, summarize_run


@dataclass(frozen=True)
class BatchRunReview:
    label: str
    base_label: str
    recipe_path: str | None
    repeat_index: int | None
    repeat_count: int | None
    run_dir: Path | None
    completed: bool | None
    points_written: int | None
    summary: RunSummary | None
    quality: dict[str, Any] | None
    error_type: str | None
    error_message: str | None


@dataclass(frozen=True)
class BatchReview:
    summary_path: Path
    batch_dir: Path
    batch_name: str
    batch_path: str | None
    dry_run: bool | None
    completed: bool | None
    checks: dict[str, Any] | None
    quality: dict[str, Any] | None
    started_at: str | None
    finished_at: str | None
    runs: list[BatchRunReview]


def resolve_batch_summary_path(path: str | Path) -> Path:
    candidate = Path(path)
    if candidate.is_dir():
        candidate = candidate / "batch_summary.json"
    if not candidate.exists():
        raise FileNotFoundError(f"Missing batch summary: {candidate}")
    return candidate


def load_batch_summary(path: str | Path) -> dict[str, Any]:
    summary_path = resolve_batch_summary_path(path)
    with summary_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{summary_path} must contain a JSON object")
    return data


def summarize_batch(path: str | Path) -> BatchReview:
    summary_path = resolve_batch_summary_path(path)
    data = load_batch_summary(summary_path)
    reviews = []
    for run in data.get("runs") or []:
        run_dir_value = run.get("run_dir")
        run_dir = Path(run_dir_value) if run_dir_value else None
        summary = None
        if run_dir is not None and (run_dir / "points.csv").exists():
            summary = summarize_run(run_dir)
        reviews.append(
            BatchRunReview(
                label=run.get("label") or "unlabeled",
                base_label=run.get("base_label") or infer_base_label(run.get("label") or "unlabeled"),
                recipe_path=run.get("recipe_path"),
                repeat_index=run.get("repeat_index"),
                repeat_count=run.get("repeat_count"),
                run_dir=run_dir,
                completed=run.get("completed"),
                points_written=run.get("points_written"),
                summary=summary,
                quality=run.get("quality"),
                error_type=run.get("error_type"),
                error_message=run.get("error_message"),
            )
        )
    return BatchReview(
        summary_path=summary_path,
        batch_dir=summary_path.parent,
        batch_name=data.get("batch_name") or summary_path.parent.name,
        batch_path=data.get("batch_path"),
        dry_run=data.get("dry_run"),
        completed=data.get("completed"),
        checks=data.get("checks"),
        quality=data.get("quality"),
        started_at=data.get("started_at"),
        finished_at=data.get("finished_at"),
        runs=reviews,
    )


def format_batch_review(review: BatchReview) -> str:
    lines = [
        f"Batch: {review.batch_name}",
        f"Summary: {review.summary_path}",
        f"Completed: {review.completed}",
        f"Dry run: {review.dry_run}",
        f"Started: {review.started_at or 'n/a'}",
        f"Finished: {review.finished_at or 'n/a'}",
        f"Runs: {len(review.runs)}",
    ]
    for index, run in enumerate(review.runs, start=1):
        resistance = None if run.summary is None else run.summary.fitted_resistance_ohm
        points = run.points_written if run.points_written is not None else (run.summary.points if run.summary else None)
        error = f", error={run.error_type}" if run.error_type else ""
        quality = f", quality={(run.quality or {}).get('status') or 'n/a'}"
        lines.append(
            (
                f"{index}. {run.label}: completed={run.completed}, points={points}, "
                f"fitted R={fmt(resistance, ' ohm')}{quality}{error}"
            )
        )
        if run.run_dir is not None:
            lines.append(f"   {run.run_dir}")
    return "\n".join(lines)


def write_batch_report(path: str | Path, output_path: str | Path | None = None) -> Path:
    review = summarize_batch(path)
    output = Path(output_path) if output_path is not None else review.batch_dir / "batch_report.md"
    output.write_text(format_batch_report(review), encoding="utf-8")
    return output


def format_batch_report(review: BatchReview) -> str:
    lines = [
        f"# {review.batch_name}",
        "",
        "## Summary",
        "",
        f"- Batch summary: `{review.summary_path}`",
        f"- Batch recipe: `{review.batch_path or 'n/a'}`",
        f"- Started: {review.started_at or 'n/a'}",
        f"- Finished: {review.finished_at or 'n/a'}",
        f"- Completed: {review.completed}",
        f"- Dry run: {review.dry_run}",
        f"- Batch QC: {(review.quality or {}).get('status') or 'n/a'}",
        f"- Runs: {len(review.runs)}",
        "",
        "## Runs",
        "",
        "| # | Label | Repeat | Completed | QC | Points | Fitted R | Error | Run directory |",
        "|---:|---|---:|---:|---|---:|---:|---|---|",
    ]
    for index, run in enumerate(review.runs, start=1):
        resistance = None if run.summary is None else run.summary.fitted_resistance_ohm
        points = run.points_written if run.points_written is not None else (run.summary.points if run.summary else None)
        lines.append(
            (
                f"| {index} | {run.label} | {format_repeat(run)} | {run.completed} | "
                f"{(run.quality or {}).get('status') or 'n/a'} | {points or 0} | "
                f"{fmt(resistance, ' ohm')} | {run.error_type or ''} | "
                f"`{run.run_dir or 'n/a'}` |"
            )
        )
    stats_rows = batch_stats_rows(review)
    if stats_rows:
        lines.extend(
            [
                "",
                "## Stability Stats",
                "",
                "| Label | Runs | Completed | QC PASS | QC FAIL | Mean R | Std R | Rel Std | Min R | Max R |",
                "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for row in stats_rows:
            lines.append(
                (
                    f"| {row['base_label']} | {row['runs']} | {row['completed']} | {row['qc_pass']} | "
                    f"{row['qc_fail']} | {fmt(row['mean_fitted_resistance_ohm'], ' ohm')} | "
                    f"{fmt(row['std_fitted_resistance_ohm'], ' ohm')} | "
                    f"{fmt(row['relative_std_percent'], ' %')} | "
                    f"{fmt(row['min_fitted_resistance_ohm'], ' ohm')} | "
                    f"{fmt(row['max_fitted_resistance_ohm'], ' ohm')} |"
                )
            )
    if review.quality:
        lines.extend(["", "## Batch Quality", "", f"- Status: {review.quality.get('status') or 'n/a'}"])
        for result in review.quality.get("results") or []:
            lines.append(
                f"- {result.get('name')}: {'PASS' if result.get('passed') else 'FAIL'} - {result.get('message')}"
            )
    if (review.batch_dir / "batch_overlay.svg").exists():
        lines.extend(["", "## Overlay Plot", "", "![Batch overlay](batch_overlay.svg)"])
    return "\n".join(lines) + "\n"


def evaluate_batch_quality(path: str | Path) -> dict[str, Any]:
    review = summarize_batch(path)
    checks = review.checks
    if not checks:
        return {"status": "SKIP", "results": []}

    results = []
    if checks.get("require_all_completed", True):
        completed = sum(1 for run in review.runs if run.completed is True)
        results.append(
            {
                "name": "all_completed",
                "passed": completed == len(review.runs) and bool(review.runs),
                "message": f"completed={completed}, total={len(review.runs)}",
            }
        )
    if checks.get("require_all_run_quality_pass", False):
        passed = sum(1 for run in review.runs if (run.quality or {}).get("status") == "PASS")
        results.append(
            {
                "name": "all_run_quality_pass",
                "passed": passed == len(review.runs) and bool(review.runs),
                "message": f"qc_pass={passed}, total={len(review.runs)}",
            }
        )
    max_relative_std = checks.get("max_relative_std_percent")
    if max_relative_std is not None:
        for row in batch_stats_rows(review):
            relative_std = row["relative_std_percent"]
            results.append(
                {
                    "name": f"relative_std_percent:{row['base_label']}",
                    "passed": relative_std is not None and relative_std <= max_relative_std,
                    "message": (
                        f"relative_std={format_optional_float(relative_std)} %, "
                        f"limit={max_relative_std:.6g} %, runs={row['runs']}"
                    ),
                }
            )
    if not results:
        return {"status": "SKIP", "results": []}
    return {"status": "PASS" if all(result["passed"] for result in results) else "FAIL", "results": results}


def update_batch_summary_quality(path: str | Path, quality: dict[str, Any]) -> Path:
    summary_path = resolve_batch_summary_path(path)
    data = load_batch_summary(summary_path)
    data["quality"] = quality
    with summary_path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, sort_keys=True, default=str)
    return summary_path


def format_batch_quality(quality: dict[str, Any]) -> str:
    lines = [f"Batch quality: {quality.get('status') or 'n/a'}"]
    for result in quality.get("results") or []:
        mark = "PASS" if result.get("passed") else "FAIL"
        lines.append(f"- {result.get('name')}: {mark} ({result.get('message')})")
    return "\n".join(lines)


def write_batch_runs_csv(path: str | Path, output_path: str | Path | None = None) -> Path:
    review = summarize_batch(path)
    output = Path(output_path) if output_path is not None else review.batch_dir / "batch_runs.csv"
    fieldnames = [
        "index",
        "label",
        "repeat_index",
        "repeat_count",
        "completed",
        "qc_status",
        "points",
        "voltage_min_v",
        "voltage_max_v",
        "current_min_a",
        "current_max_a",
        "fitted_resistance_ohm",
        "error_type",
        "run_dir",
        "recipe_path",
    ]
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for index, run in enumerate(review.runs, start=1):
            summary = run.summary
            writer.writerow(
                {
                    "index": index,
                    "label": run.label,
                    "repeat_index": run.repeat_index,
                    "repeat_count": run.repeat_count,
                    "completed": run.completed,
                    "qc_status": (run.quality or {}).get("status"),
                    "points": run.points_written if run.points_written is not None else (summary.points if summary else None),
                    "voltage_min_v": None if summary is None else summary.voltage_min_v,
                    "voltage_max_v": None if summary is None else summary.voltage_max_v,
                    "current_min_a": None if summary is None else summary.current_min_a,
                    "current_max_a": None if summary is None else summary.current_max_a,
                    "fitted_resistance_ohm": None if summary is None else summary.fitted_resistance_ohm,
                    "error_type": run.error_type,
                    "run_dir": run.run_dir,
                    "recipe_path": run.recipe_path,
                }
            )
    return output


def write_batch_points_csv(path: str | Path, output_path: str | Path | None = None) -> Path:
    review = summarize_batch(path)
    output = Path(output_path) if output_path is not None else review.batch_dir / "batch_points.csv"
    fieldnames = [
        "batch_index",
        "label",
        "base_label",
        "repeat_index",
        "repeat_count",
        "run_dir",
        "point_index",
        "voltage_v",
        "current_a",
        "elapsed_s",
        "resistance_ohm",
        "compliance_hit",
    ]
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for batch_index, run in enumerate(review.runs, start=1):
            if run.run_dir is None:
                continue
            points_path = run.run_dir / "points.csv"
            if not points_path.exists():
                continue
            for point in read_raw_point_rows(points_path):
                writer.writerow(
                    {
                        "batch_index": batch_index,
                        "label": run.label,
                        "base_label": run.base_label,
                        "repeat_index": run.repeat_index,
                        "repeat_count": run.repeat_count,
                        "run_dir": run.run_dir,
                        "point_index": point.get("index"),
                        "voltage_v": point.get("voltage_v"),
                        "current_a": point.get("current_a"),
                        "elapsed_s": point.get("elapsed_s"),
                        "resistance_ohm": point.get("resistance_ohm"),
                        "compliance_hit": point.get("compliance_hit"),
                    }
                )
    return output


def read_raw_point_rows(points_path: Path) -> list[dict[str, str]]:
    with points_path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_batch_stats_csv(path: str | Path, output_path: str | Path | None = None) -> Path:
    review = summarize_batch(path)
    output = Path(output_path) if output_path is not None else review.batch_dir / "batch_stats.csv"
    fieldnames = [
        "base_label",
        "runs",
        "completed",
        "qc_pass",
        "qc_fail",
        "mean_fitted_resistance_ohm",
        "std_fitted_resistance_ohm",
        "relative_std_percent",
        "min_fitted_resistance_ohm",
        "max_fitted_resistance_ohm",
    ]
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in batch_stats_rows(review):
            writer.writerow(row)
    return output


def batch_stats_rows(review: BatchReview) -> list[dict[str, Any]]:
    rows = []
    for base_label in sorted({run.base_label for run in review.runs}):
        group = [run for run in review.runs if run.base_label == base_label]
        resistances = [
            run.summary.fitted_resistance_ohm
            for run in group
            if run.summary is not None and run.summary.fitted_resistance_ohm is not None
        ]
        mean = mean_value(resistances)
        std = sample_std(resistances)
        relative_std = None if mean in {None, 0} or std is None else abs(std / mean) * 100
        qc_pass = sum(1 for run in group if (run.quality or {}).get("status") == "PASS")
        qc_fail = sum(1 for run in group if (run.quality or {}).get("status") == "FAIL")
        rows.append(
            {
                "base_label": base_label,
                "runs": len(group),
                "completed": sum(1 for run in group if run.completed is True),
                "qc_pass": qc_pass,
                "qc_fail": qc_fail,
                "mean_fitted_resistance_ohm": mean,
                "std_fitted_resistance_ohm": std,
                "relative_std_percent": relative_std,
                "min_fitted_resistance_ohm": min(resistances) if resistances else None,
                "max_fitted_resistance_ohm": max(resistances) if resistances else None,
            }
        )
    return rows


def mean_value(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def sample_std(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    mean = mean_value(values)
    if mean is None:
        return None
    return (sum((value - mean) ** 2 for value in values) / (len(values) - 1)) ** 0.5


def infer_base_label(label: str) -> str:
    if len(label) > 6 and label[-6:-2] == "_rep" and label[-2:].isdigit():
        return label[:-6]
    return label


def format_repeat(run: BatchRunReview) -> str:
    if run.repeat_index is None or run.repeat_count is None:
        return "n/a"
    return f"{run.repeat_index}/{run.repeat_count}"


def format_optional_float(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.6g}"


def write_batch_overlay_svg(path: str | Path, output_path: str | Path | None = None) -> Path:
    review = summarize_batch(path)
    output = Path(output_path) if output_path is not None else review.batch_dir / "batch_overlay.svg"
    series = []
    for run in review.runs:
        if run.run_dir is None or not (run.run_dir / "points.csv").exists():
            continue
        points = read_points(run.run_dir)
        if points:
            series.append((run.label, points))
    if not series:
        raise ValueError(f"No plottable runs in {review.summary_path}")

    voltages = [point["voltage_v"] for _, points in series for point in points]
    currents = [point["current_a"] for _, points in series for point in points]
    v_min, v_max = min(voltages), max(voltages)
    i_min, i_max = min(currents), max(currents)
    if v_min == v_max:
        v_min -= 1
        v_max += 1
    if i_min == i_max:
        i_min -= 1
        i_max += 1

    width, height = 840, 600
    left, right, top, bottom = 92, 190, 78, 74
    plot_w = width - left - right
    plot_h = height - top - bottom
    colors = ["#0f766e", "#2563eb", "#b45309", "#7c3aed", "#be123c", "#15803d"]
    polylines = []
    legend = []
    for index, (label, points) in enumerate(series):
        color = colors[index % len(colors)]
        polyline_points = []
        for point in points:
            x = _scale(point["voltage_v"], v_min, v_max, left, left + plot_w)
            y = _scale(point["current_a"], i_min, i_max, top + plot_h, top)
            polyline_points.append(f"{x:.2f},{y:.2f}")
        polylines.append(
            f'<polyline points="{" ".join(polyline_points)}" fill="none" stroke="{color}" stroke-width="2.2" />'
        )
        legend_y = top + 22 * index
        legend.append(
            (
                f'<line x1="{left + plot_w + 24}" y1="{legend_y}" x2="{left + plot_w + 48}" y2="{legend_y}" '
                f'stroke="{color}" stroke-width="3" />'
                f'<text x="{left + plot_w + 56}" y="{legend_y + 4}" font-family="Arial, sans-serif" '
                f'font-size="12" fill="#111827">{escape(label)}</text>'
            )
        )

    zero_x = _scale(0, v_min, v_max, left, left + plot_w) if v_min <= 0 <= v_max else None
    zero_y = _scale(0, i_min, i_max, top + plot_h, top) if i_min <= 0 <= i_max else None
    axis_lines = []
    if zero_x is not None:
        axis_lines.append(
            f'<line x1="{zero_x:.2f}" y1="{top}" x2="{zero_x:.2f}" y2="{top + plot_h}" stroke="#d1d5db" />'
        )
    if zero_y is not None:
        axis_lines.append(
            f'<line x1="{left}" y1="{zero_y:.2f}" x2="{left + plot_w}" y2="{zero_y:.2f}" stroke="#d1d5db" />'
        )

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <rect width="100%" height="100%" fill="#ffffff" />
  <text x="{left}" y="30" font-family="Arial, sans-serif" font-size="18" fill="#111827">{escape(review.batch_name)}</text>
  <text x="{left}" y="54" font-family="Arial, sans-serif" font-size="13" fill="#374151">runs={len(series)}, completed={review.completed}, dry_run={review.dry_run}</text>
  <rect x="{left}" y="{top}" width="{plot_w}" height="{plot_h}" fill="#f9fafb" stroke="#9ca3af" />
  {''.join(axis_lines)}
  {''.join(polylines)}
  {''.join(legend)}
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
