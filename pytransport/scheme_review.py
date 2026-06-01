"""Review artifacts for completed measurement schemes."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Any

from .batch_review import (
    read_raw_point_rows,
    summarize_batch,
)
from .method_registry import handler_for_scheme_step
from .plot import _scale
from .report import fmt
from .single_gate_review import SingleGateSummary, read_single_gate_points
from .summary import RunSummary, read_points


@dataclass(frozen=True)
class SchemeRunReview:
    step_label: str
    label: str
    type: str
    run_dir: Path | None
    completed: bool | None
    summary: RunSummary | SingleGateSummary | None
    quality: dict[str, Any] | None
    error_type: str | None
    metadata_path: str | None
    source_summary_path: str | None


@dataclass(frozen=True)
class SchemeReview:
    summary_path: Path
    scheme_dir: Path
    scheme_name: str
    scheme_path: str | None
    dry_run: bool | None
    completed: bool | None
    quality: dict[str, Any] | None
    started_at: str | None
    finished_at: str | None
    runs: list[SchemeRunReview]


def resolve_scheme_summary_path(path: str | Path) -> Path:
    candidate = Path(path)
    if candidate.is_dir():
        candidate = candidate / "scheme_summary.json"
    if not candidate.exists():
        raise FileNotFoundError(f"Missing scheme summary: {candidate}")
    return candidate


def load_scheme_summary(path: str | Path) -> dict[str, Any]:
    summary_path = resolve_scheme_summary_path(path)
    with summary_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{summary_path} must contain a JSON object")
    return data


def summarize_scheme(path: str | Path) -> SchemeReview:
    summary_path = resolve_scheme_summary_path(path)
    data = load_scheme_summary(summary_path)
    runs: list[SchemeRunReview] = []
    for step in data.get("steps") or []:
        if step.get("type") == "batch" and step.get("batch_summary_path"):
            batch_review = summarize_batch(step["batch_summary_path"])
            for batch_run in batch_review.runs:
                runs.append(
                    SchemeRunReview(
                        step_label=step.get("label") or "unlabeled",
                        label=f"{step.get('label') or 'batch'}:{batch_run.label}",
                        type="batch_run",
                        run_dir=batch_run.run_dir,
                        completed=batch_run.completed,
                        summary=batch_run.summary,
                        quality=batch_run.quality,
                        error_type=batch_run.error_type,
                        metadata_path=None,
                        source_summary_path=str(batch_review.summary_path),
                    )
                )
            continue
        run_dir_value = step.get("run_dir")
        run_dir = Path(run_dir_value) if run_dir_value else None
        summary = None
        if run_dir is not None and (run_dir / "points.csv").exists():
            summary = handler_for_scheme_step(step.get("type")).summarize(run_dir)
        runs.append(
            SchemeRunReview(
                step_label=step.get("label") or "unlabeled",
                label=step.get("label") or "unlabeled",
                type=step.get("type") or "unknown",
                run_dir=run_dir,
                completed=step.get("completed"),
                summary=summary,
                quality=step.get("quality"),
                error_type=step.get("error_type"),
                metadata_path=step.get("metadata_path"),
                source_summary_path=None,
            )
        )
    return SchemeReview(
        summary_path=summary_path,
        scheme_dir=summary_path.parent,
        scheme_name=data.get("scheme_name") or summary_path.parent.name,
        scheme_path=data.get("scheme_path"),
        dry_run=data.get("dry_run"),
        completed=data.get("completed"),
        quality=data.get("quality"),
        started_at=data.get("started_at"),
        finished_at=data.get("finished_at"),
        runs=runs,
    )


def evaluate_scheme_quality(path: str | Path) -> dict[str, Any]:
    review = summarize_scheme(path)
    completed = sum(1 for run in review.runs if run.completed is True)
    failed_qc = [run for run in review.runs if (run.quality or {}).get("status") == "FAIL"]
    results = [
        {
            "name": "all_completed",
            "passed": completed == len(review.runs) and bool(review.runs),
            "message": f"completed={completed}, total={len(review.runs)}",
        },
        {
            "name": "no_run_quality_failures",
            "passed": not failed_qc,
            "message": f"failed_qc={len(failed_qc)}, total={len(review.runs)}",
        },
    ]
    return {"status": "PASS" if all(result["passed"] for result in results) else "FAIL", "results": results}


def update_scheme_summary_quality(path: str | Path, quality: dict[str, Any]) -> Path:
    summary_path = resolve_scheme_summary_path(path)
    data = load_scheme_summary(summary_path)
    data["quality"] = quality
    with summary_path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, sort_keys=True, default=str)
    return summary_path


def format_scheme_quality(quality: dict[str, Any]) -> str:
    lines = [f"Scheme quality: {quality.get('status') or 'n/a'}"]
    for result in quality.get("results") or []:
        mark = "PASS" if result.get("passed") else "FAIL"
        lines.append(f"- {result.get('name')}: {mark} ({result.get('message')})")
    return "\n".join(lines)


def write_scheme_report(path: str | Path, output_path: str | Path | None = None) -> Path:
    review = summarize_scheme(path)
    output = Path(output_path) if output_path is not None else review.scheme_dir / "scheme_report.md"
    output.write_text(format_scheme_report(review), encoding="utf-8")
    return output


def format_scheme_report(review: SchemeReview) -> str:
    lines = [
        f"# {review.scheme_name}",
        "",
        "## Summary",
        "",
        f"- Scheme summary: `{review.summary_path}`",
        f"- Scheme recipe: `{review.scheme_path or 'n/a'}`",
        f"- Started: {review.started_at or 'n/a'}",
        f"- Finished: {review.finished_at or 'n/a'}",
        f"- Completed: {review.completed}",
        f"- Dry run: {review.dry_run}",
        f"- Scheme QC: {(review.quality or {}).get('status') or 'n/a'}",
        f"- Runs: {len(review.runs)}",
        "",
        "## Runs",
        "",
        "| # | Step | Label | Type | Completed | QC | Points | Fitted R | Gate points | Gate leakage max | Error | Run directory |",
        "|---:|---|---|---|---:|---|---:|---:|---:|---:|---|---|",
    ]
    for index, run in enumerate(review.runs, start=1):
        summary = run.summary
        lines.append(
            (
                f"| {index} | {run.step_label} | {run.label} | {run.type} | {run.completed} | "
                f"{(run.quality or {}).get('status') or 'n/a'} | "
                f"{summary.points if summary is not None else 0} | "
                f"{fmt(fitted_resistance(summary), ' ohm')} | "
                f"{fmt(gate_points(summary))} | "
                f"{fmt(gate_leakage_abs_max(summary), ' A')} | "
                f"{run.error_type or ''} | `{run.run_dir or 'n/a'}` |"
            )
        )
    stats_rows = scheme_stats_rows(review)
    if stats_rows:
        lines.extend(
            [
                "",
                "## Run Stats",
                "",
                "| Step | Runs | Completed | QC PASS | QC FAIL | Mean R | Std R | Rel Std | Min R | Max R |",
                "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for row in stats_rows:
            lines.append(
                (
                    f"| {row['step_label']} | {row['runs']} | {row['completed']} | {row['qc_pass']} | "
                    f"{row['qc_fail']} | {fmt(row['mean_fitted_resistance_ohm'], ' ohm')} | "
                    f"{fmt(row['std_fitted_resistance_ohm'], ' ohm')} | "
                    f"{fmt(row['relative_std_percent'], ' %')} | "
                    f"{fmt(row['min_fitted_resistance_ohm'], ' ohm')} | "
                    f"{fmt(row['max_fitted_resistance_ohm'], ' ohm')} |"
                )
            )
    if review.quality:
        lines.extend(["", "## Scheme Quality", "", f"- Status: {review.quality.get('status') or 'n/a'}"])
        for result in review.quality.get("results") or []:
            lines.append(
                f"- {result.get('name')}: {'PASS' if result.get('passed') else 'FAIL'} - {result.get('message')}"
            )
    if (review.scheme_dir / "scheme_overlay.svg").exists():
        lines.extend(["", "## Overlay Plot", "", "![Scheme overlay](scheme_overlay.svg)"])
    return "\n".join(lines) + "\n"


def write_scheme_runs_csv(path: str | Path, output_path: str | Path | None = None) -> Path:
    review = summarize_scheme(path)
    output = Path(output_path) if output_path is not None else review.scheme_dir / "scheme_runs.csv"
    fieldnames = [
        "index",
        "step_label",
        "label",
        "type",
        "completed",
        "qc_status",
        "points",
        "voltage_min_v",
        "voltage_max_v",
        "current_min_a",
        "current_max_a",
        "fitted_resistance_ohm",
        "gate_points",
        "drain_points",
        "gate_leakage_abs_max_a",
        "error_type",
        "run_dir",
        "metadata_path",
        "source_summary_path",
    ]
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for index, run in enumerate(review.runs, start=1):
            summary = run.summary
            writer.writerow(
                {
                    "index": index,
                    "step_label": run.step_label,
                    "label": run.label,
                    "type": run.type,
                    "completed": run.completed,
                    "qc_status": (run.quality or {}).get("status"),
                    "points": None if summary is None else summary.points,
                    "voltage_min_v": voltage_min(summary),
                    "voltage_max_v": voltage_max(summary),
                    "current_min_a": current_min(summary),
                    "current_max_a": current_max(summary),
                    "fitted_resistance_ohm": fitted_resistance(summary),
                    "gate_points": gate_points(summary),
                    "drain_points": drain_points(summary),
                    "gate_leakage_abs_max_a": gate_leakage_abs_max(summary),
                    "error_type": run.error_type,
                    "run_dir": run.run_dir,
                    "metadata_path": run.metadata_path,
                    "source_summary_path": run.source_summary_path,
                }
            )
    return output


def write_scheme_points_csv(path: str | Path, output_path: str | Path | None = None) -> Path:
    review = summarize_scheme(path)
    output = Path(output_path) if output_path is not None else review.scheme_dir / "scheme_points.csv"
    fieldnames = [
        "scheme_index",
        "step_label",
        "label",
        "type",
        "run_dir",
        "point_index",
        "voltage_v",
        "current_a",
        "elapsed_s",
        "resistance_ohm",
        "compliance_hit",
        "gate_index",
        "drain_index",
        "gate_voltage_v",
        "drain_voltage_v",
        "drain_current_a",
        "gate_current_a",
        "drain_compliance_hit",
        "gate_compliance_hit",
    ]
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for scheme_index, run in enumerate(review.runs, start=1):
            if run.run_dir is None:
                continue
            points_path = run.run_dir / "points.csv"
            if not points_path.exists():
                continue
            for point in read_scheme_point_rows(run):
                writer.writerow(
                    {
                        "scheme_index": scheme_index,
                        "step_label": run.step_label,
                        "label": run.label,
                        "type": run.type,
                        "run_dir": run.run_dir,
                        "point_index": point.get("index"),
                        "voltage_v": point.get("voltage_v"),
                        "current_a": point.get("current_a"),
                        "elapsed_s": point.get("elapsed_s"),
                        "resistance_ohm": point.get("resistance_ohm"),
                        "compliance_hit": point.get("compliance_hit"),
                        "gate_index": point.get("gate_index"),
                        "drain_index": point.get("drain_index"),
                        "gate_voltage_v": point.get("gate_voltage_v"),
                        "drain_voltage_v": point.get("drain_voltage_v"),
                        "drain_current_a": point.get("drain_current_a"),
                        "gate_current_a": point.get("gate_current_a"),
                        "drain_compliance_hit": point.get("drain_compliance_hit"),
                        "gate_compliance_hit": point.get("gate_compliance_hit"),
                    }
                )
    return output


def write_scheme_stats_csv(path: str | Path, output_path: str | Path | None = None) -> Path:
    review = summarize_scheme(path)
    output = Path(output_path) if output_path is not None else review.scheme_dir / "scheme_stats.csv"
    fieldnames = [
        "step_label",
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
        for row in scheme_stats_rows(review):
            writer.writerow(row)
    return output


def scheme_stats_rows(review: SchemeReview) -> list[dict[str, Any]]:
    rows = []
    for step_label in sorted({run.step_label for run in review.runs}):
        group = [run for run in review.runs if run.step_label == step_label]
        resistances = [
            fitted_resistance(run.summary)
            for run in group
            if run.summary is not None and fitted_resistance(run.summary) is not None
        ]
        batch_like = batch_stats_rows_for_values(step_label, group, resistances)
        rows.append(batch_like)
    return rows


def batch_stats_rows_for_values(step_label: str, group: list[SchemeRunReview], resistances: list[float]) -> dict[str, Any]:
    mean = sum(resistances) / len(resistances) if resistances else None
    std = None
    if len(resistances) >= 2 and mean is not None:
        std = (sum((value - mean) ** 2 for value in resistances) / (len(resistances) - 1)) ** 0.5
    relative_std = None if mean in {None, 0} or std is None else abs(std / mean) * 100
    return {
        "step_label": step_label,
        "runs": len(group),
        "completed": sum(1 for run in group if run.completed is True),
        "qc_pass": sum(1 for run in group if (run.quality or {}).get("status") == "PASS"),
        "qc_fail": sum(1 for run in group if (run.quality or {}).get("status") == "FAIL"),
        "mean_fitted_resistance_ohm": mean,
        "std_fitted_resistance_ohm": std,
        "relative_std_percent": relative_std,
        "min_fitted_resistance_ohm": min(resistances) if resistances else None,
        "max_fitted_resistance_ohm": max(resistances) if resistances else None,
    }


def write_scheme_overlay_svg(path: str | Path, output_path: str | Path | None = None) -> Path:
    review = summarize_scheme(path)
    output = Path(output_path) if output_path is not None else review.scheme_dir / "scheme_overlay.svg"
    series = []
    for run in review.runs:
        if run.type == "single_gate" or run.run_dir is None or not (run.run_dir / "points.csv").exists():
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

    width, height = 900, 620
    left, right, top, bottom = 92, 230, 78, 74
    plot_w = width - left - right
    plot_h = height - top - bottom
    colors = ["#0f766e", "#2563eb", "#b45309", "#7c3aed", "#be123c", "#15803d", "#0891b2", "#4d7c0f"]
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
  <text x="{left}" y="30" font-family="Arial, sans-serif" font-size="18" fill="#111827">{escape(review.scheme_name)}</text>
  <text x="{left}" y="54" font-family="Arial, sans-serif" font-size="13" fill="#374151">runs={len(series)}, completed={review.completed}, quality={(review.quality or {}).get('status') or 'n/a'}, dry_run={review.dry_run}</text>
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


def fitted_resistance(summary: RunSummary | SingleGateSummary | None) -> float | None:
    return getattr(summary, "fitted_resistance_ohm", None)


def voltage_min(summary: RunSummary | SingleGateSummary | None) -> float | None:
    if isinstance(summary, SingleGateSummary):
        return summary.drain_voltage_min_v
    return getattr(summary, "voltage_min_v", None)


def voltage_max(summary: RunSummary | SingleGateSummary | None) -> float | None:
    if isinstance(summary, SingleGateSummary):
        return summary.drain_voltage_max_v
    return getattr(summary, "voltage_max_v", None)


def current_min(summary: RunSummary | SingleGateSummary | None) -> float | None:
    if isinstance(summary, SingleGateSummary):
        return summary.drain_current_min_a
    return getattr(summary, "current_min_a", None)


def current_max(summary: RunSummary | SingleGateSummary | None) -> float | None:
    if isinstance(summary, SingleGateSummary):
        return summary.drain_current_max_a
    return getattr(summary, "current_max_a", None)


def gate_points(summary: RunSummary | SingleGateSummary | None) -> int | None:
    return getattr(summary, "gate_points", None)


def drain_points(summary: RunSummary | SingleGateSummary | None) -> int | None:
    return getattr(summary, "drain_points", None)


def gate_leakage_abs_max(summary: RunSummary | SingleGateSummary | None) -> float | None:
    return getattr(summary, "gate_leakage_abs_max_a", None)


def read_scheme_point_rows(run: SchemeRunReview) -> list[dict[str, Any]]:
    if run.run_dir is None:
        return []
    if run.type == "single_gate":
        return [dict(point) for point in read_single_gate_points(run.run_dir)]
    return read_raw_point_rows(run.run_dir / "points.csv")
