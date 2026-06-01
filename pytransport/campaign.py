"""Campaign-level manifests across runs, batches, and schemes."""

from __future__ import annotations

import csv
import json
import shutil
from dataclasses import dataclass
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any

from .batch import safe_name
from .io import unique_run_dir
from .method_registry import handler_for_metadata, handler_for_measurement_type, measurement_type_from_metadata
from .report import fmt


@dataclass(frozen=True)
class CampaignPaths:
    campaign_dir: Path
    manifest_path: Path
    runs_csv_path: Path
    report_path: Path
    stats_csv_path: Path | None = None
    histogram_path: Path | None = None


@dataclass(frozen=True)
class CampaignBundlePaths:
    bundle_dir: Path
    bundle_manifest_path: Path
    zip_path: Path


@dataclass(frozen=True)
class CampaignFilters:
    sample_id: str | None = None
    device_id: str | None = None
    tag: str | None = None
    quality_status: str | None = None
    completed: bool | None = None
    failed_only: bool = False
    measurement_contains: str | None = None
    min_resistance_ohm: float | None = None
    max_resistance_ohm: float | None = None

    def active(self) -> bool:
        return any(
            [
                self.sample_id is not None,
                self.device_id is not None,
                self.tag is not None,
                self.quality_status is not None,
                self.completed is not None,
                self.failed_only,
                self.measurement_contains is not None,
                self.min_resistance_ohm is not None,
                self.max_resistance_ohm is not None,
            ]
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "sample_id": self.sample_id,
            "device_id": self.device_id,
            "tag": self.tag,
            "quality_status": self.quality_status,
            "completed": self.completed,
            "failed_only": self.failed_only,
            "measurement_contains": self.measurement_contains,
            "min_resistance_ohm": self.min_resistance_ohm,
            "max_resistance_ohm": self.max_resistance_ohm,
        }


def create_campaign(
    name: str,
    raw_dir: str | Path = "data/raw",
    batch_dir: str | Path = "data/batches",
    scheme_dir: str | Path = "data/schemes",
    output_dir: str | Path = "data/campaigns",
    filters: CampaignFilters | None = None,
    analytics: bool = False,
) -> CampaignPaths:
    campaign_dir = unique_run_dir(
        Path(output_dir),
        f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{safe_name(name)}",
    )
    campaign_dir.mkdir(parents=True, exist_ok=False)
    manifest = build_campaign_manifest(name, raw_dir, batch_dir, scheme_dir, filters)
    manifest_path = campaign_dir / "campaign_manifest.json"
    write_json(manifest_path, manifest)
    runs_csv_path = write_campaign_runs_csv(manifest, campaign_dir / "campaign_runs.csv")
    stats_csv_path = None
    histogram_path = None
    if analytics:
        stats_csv_path = write_campaign_stats_csv(manifest, campaign_dir / "campaign_stats.csv")
        if campaign_has_fitted_resistance_values(manifest):
            histogram_path = write_campaign_resistance_histogram_svg(
                manifest,
                campaign_dir / "campaign_resistance_histogram.svg",
            )
    report_path = write_campaign_report(manifest, campaign_dir / "campaign_report.md")
    return CampaignPaths(campaign_dir, manifest_path, runs_csv_path, report_path, stats_csv_path, histogram_path)


def build_campaign_manifest(
    name: str,
    raw_dir: str | Path = "data/raw",
    batch_dir: str | Path = "data/batches",
    scheme_dir: str | Path = "data/schemes",
    filters: CampaignFilters | None = None,
) -> dict[str, Any]:
    raw_path = Path(raw_dir)
    batch_path = Path(batch_dir)
    scheme_path = Path(scheme_dir)
    all_runs = collect_runs(raw_path)
    active_filters = filters or CampaignFilters()
    runs = filter_runs(all_runs, active_filters)
    batches = collect_summaries(batch_path, "batch_summary.json")
    schemes = collect_summaries(scheme_path, "scheme_summary.json")
    return {
        "campaign_name": name,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "roots": {
            "raw_dir": str(raw_path),
            "batch_dir": str(batch_path),
            "scheme_dir": str(scheme_path),
        },
        "filters": active_filters.to_dict(),
        "counts": campaign_counts(runs, batches, schemes),
        "source_counts": {"runs": len(all_runs), "batches": len(batches), "schemes": len(schemes)},
        "runs": runs,
        "batches": batches,
        "schemes": schemes,
    }


def filter_runs(runs: list[dict[str, Any]], filters: CampaignFilters) -> list[dict[str, Any]]:
    if not filters.active():
        return runs
    return [run for run in runs if run_matches_filters(run, filters)]


def run_matches_filters(run: dict[str, Any], filters: CampaignFilters) -> bool:
    if filters.sample_id is not None and run.get("sample_id") != filters.sample_id:
        return False
    if filters.device_id is not None and run.get("device_id") != filters.device_id:
        return False
    if filters.tag is not None and filters.tag not in (run.get("tags") or []):
        return False
    if filters.quality_status is not None and (run.get("quality_status") or "n/a") != filters.quality_status:
        return False
    if filters.completed is not None and run.get("completed") is not filters.completed:
        return False
    if filters.failed_only and not run.get("error_type"):
        return False
    if filters.measurement_contains is not None:
        needle = filters.measurement_contains.lower()
        if needle not in str(run.get("measurement_name") or "").lower():
            return False
    resistance = run.get("fitted_resistance_ohm")
    if filters.min_resistance_ohm is not None:
        if resistance is None or resistance < filters.min_resistance_ohm:
            return False
    if filters.max_resistance_ohm is not None:
        if resistance is None or resistance > filters.max_resistance_ohm:
            return False
    return True


def collect_runs(raw_dir: Path) -> list[dict[str, Any]]:
    if not raw_dir.exists():
        return []
    records = []
    for metadata_path in sorted(raw_dir.glob("*/metadata.json")):
        data = read_json(metadata_path)
        run_dir = metadata_path.parent
        summary = None
        if (run_dir / "points.csv").exists():
            try:
                summary = summarize_saved_run(run_dir, data)
            except Exception as exc:
                summary = {"error": f"{type(exc).__name__}: {exc}"}
        recipe = data.get("recipe") or {}
        experiment = recipe.get("experiment") or {}
        quality = data.get("quality") or {}
        record = {
            "run_dir": str(run_dir),
            "metadata_path": str(metadata_path),
            "measurement_name": data.get("measurement_name"),
            "measurement_type": measurement_type_from_metadata(data),
            "started_at": data.get("started_at"),
            "finished_at": data.get("finished_at"),
            "completed": data.get("completed"),
            "interrupted": data.get("interrupted"),
            "error_type": data.get("error_type"),
            "error_message": data.get("error_message"),
            "points_written": data.get("points_written"),
            "sample_id": experiment.get("sample_id"),
            "device_id": experiment.get("device_id"),
            "operator": experiment.get("operator"),
            "tags": experiment.get("tags") or [],
            "recipe_path": data.get("recipe_path"),
            "quality_status": quality.get("status"),
            "fitted_resistance_ohm": None,
            "voltage_min_v": None,
            "voltage_max_v": None,
            "current_min_a": None,
            "current_max_a": None,
            "gate_points": None,
            "drain_points": None,
            "gate_voltage_min_v": None,
            "gate_voltage_max_v": None,
            "drain_voltage_min_v": None,
            "drain_voltage_max_v": None,
            "drain_current_min_a": None,
            "drain_current_max_a": None,
            "gate_current_min_a": None,
            "gate_current_max_a": None,
            "gate_leakage_abs_max_a": None,
            "lockin_r_min_v": None,
            "lockin_r_max_v": None,
            "lockin_theta_min_deg": None,
            "lockin_theta_max_deg": None,
            "pulse_voltage_v": None,
            "pulse_width_s": None,
            "pulse_period_s": None,
            "pulse_duty_cycle": None,
        }
        if summary is not None and not isinstance(summary, dict):
            record.update(campaign_summary_fields(summary, record["measurement_type"]))
        elif isinstance(summary, dict):
            record["summary_error"] = summary.get("error")
        records.append(record)
    return records


def summarize_saved_run(run_dir: Path, metadata: dict[str, Any]):
    return handler_for_metadata(metadata).summarize(run_dir)


def campaign_summary_fields(summary, measurement_type: str) -> dict[str, Any]:
    return handler_for_measurement_type(measurement_type).campaign_summary_fields(summary)


def collect_summaries(root: Path, filename: str) -> list[dict[str, Any]]:
    if not root.exists():
        return []
    records = []
    for summary_path in sorted(root.rglob(filename)):
        data = read_json(summary_path)
        quality = data.get("quality") or {}
        if filename == "batch_summary.json":
            runs = data.get("runs") or []
            records.append(
                {
                    "summary_path": str(summary_path),
                    "name": data.get("batch_name") or summary_path.parent.name,
                    "recipe_path": data.get("batch_path"),
                    "started_at": data.get("started_at"),
                    "finished_at": data.get("finished_at"),
                    "dry_run": data.get("dry_run"),
                    "completed": data.get("completed"),
                    "quality_status": quality.get("status"),
                    "runs": len(runs),
                    "completed_runs": sum(1 for run in runs if run.get("completed") is True),
                }
            )
        else:
            steps = data.get("steps") or []
            records.append(
                {
                    "summary_path": str(summary_path),
                    "name": data.get("scheme_name") or summary_path.parent.name,
                    "recipe_path": data.get("scheme_path"),
                    "started_at": data.get("started_at"),
                    "finished_at": data.get("finished_at"),
                    "dry_run": data.get("dry_run"),
                    "completed": data.get("completed"),
                    "quality_status": quality.get("status"),
                    "steps": len(steps),
                    "completed_steps": sum(1 for step in steps if step.get("completed") is True),
                }
            )
    return records


def campaign_counts(
    runs: list[dict[str, Any]],
    batches: list[dict[str, Any]],
    schemes: list[dict[str, Any]],
) -> dict[str, Any]:
    qc_counts: dict[str, int] = {}
    for run in runs:
        status = run.get("quality_status") or "n/a"
        qc_counts[status] = qc_counts.get(status, 0) + 1
    return {
        "runs": len(runs),
        "completed_runs": sum(1 for run in runs if run.get("completed") is True),
        "failed_runs": sum(1 for run in runs if run.get("error_type")),
        "interrupted_runs": sum(1 for run in runs if run.get("interrupted")),
        "run_quality": qc_counts,
        "run_types": run_type_counts(runs),
        "batches": len(batches),
        "completed_batches": sum(1 for batch in batches if batch.get("completed") is True),
        "schemes": len(schemes),
        "completed_schemes": sum(1 for scheme in schemes if scheme.get("completed") is True),
    }


def run_type_counts(runs: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for run in runs:
        measurement_type = run.get("measurement_type") or "drain_iv"
        counts[measurement_type] = counts.get(measurement_type, 0) + 1
    return counts


def write_campaign_runs_csv(manifest: dict[str, Any], output_path: str | Path) -> Path:
    output = Path(output_path)
    fieldnames = [
        "index",
        "measurement_name",
        "measurement_type",
        "started_at",
        "completed",
        "quality_status",
        "points",
        "points_written",
        "sample_id",
        "device_id",
        "operator",
        "tags",
        "fitted_resistance_ohm",
        "gate_points",
        "drain_points",
        "gate_voltage_min_v",
        "gate_voltage_max_v",
        "gate_leakage_abs_max_a",
        "lockin_r_min_v",
        "lockin_r_max_v",
        "lockin_theta_min_deg",
        "lockin_theta_max_deg",
        "pulse_voltage_v",
        "pulse_width_s",
        "pulse_period_s",
        "pulse_duty_cycle",
        "voltage_min_v",
        "voltage_max_v",
        "current_min_a",
        "current_max_a",
        "error_type",
        "run_dir",
        "recipe_path",
    ]
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for index, run in enumerate(manifest.get("runs") or [], start=1):
            writer.writerow(
                {
                    "index": index,
                    **{
                        key: ", ".join(run.get(key) or []) if key == "tags" else run.get(key)
                        for key in fieldnames
                        if key != "index"
                    },
                }
            )
    return output


def export_campaign_bundle(
    campaign_manifest_or_dir: str | Path,
    output_dir: str | Path = "data/exports",
    include_points: bool = True,
    include_plots: bool = True,
    include_reports: bool = True,
) -> CampaignBundlePaths:
    manifest_path = resolve_campaign_manifest_path(campaign_manifest_or_dir)
    manifest = load_campaign_manifest(manifest_path)
    bundle_dir = unique_run_dir(
        Path(output_dir),
        f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{safe_name(str(manifest.get('campaign_name') or 'campaign'))}_bundle",
    )
    bundle_dir.mkdir(parents=True, exist_ok=False)
    copied_files: list[dict[str, str]] = []

    campaign_files_dir = bundle_dir / "campaign"
    campaign_files_dir.mkdir()
    for filename in [
        "campaign_manifest.json",
        "campaign_runs.csv",
        "campaign_stats.csv",
        "campaign_report.md",
        "campaign_resistance_histogram.svg",
    ]:
        source = manifest_path.with_name(filename)
        if source.exists():
            copied_files.append(copy_file_record(source, campaign_files_dir / filename, "campaign"))

    runs_dir = bundle_dir / "runs"
    runs_dir.mkdir()
    for index, run in enumerate(manifest.get("runs") or [], start=1):
        run_dir_value = run.get("run_dir")
        if not run_dir_value:
            continue
        source_run_dir = Path(run_dir_value)
        if not source_run_dir.exists():
            continue
        target_run_dir = runs_dir / f"{index:03d}_{safe_name(source_run_dir.name)}"
        target_run_dir.mkdir()
        for filename in run_bundle_filenames(include_points, include_plots, include_reports):
            source = source_run_dir / filename
            if source.exists():
                copied_files.append(copy_file_record(source, target_run_dir / filename, "run"))

    summaries_dir = bundle_dir / "summaries"
    summaries_dir.mkdir()
    for collection_name, summary_key in [("batches", "batches"), ("schemes", "schemes")]:
        target_root = summaries_dir / collection_name
        target_root.mkdir()
        for index, record in enumerate(manifest.get(summary_key) or [], start=1):
            source_value = record.get("summary_path")
            if not source_value:
                continue
            source = Path(source_value)
            if source.exists():
                target = target_root / f"{index:03d}_{safe_name(source.parent.name)}_{source.name}"
                copied_files.append(copy_file_record(source, target, collection_name))

    bundle_manifest = {
        "campaign_name": manifest.get("campaign_name"),
        "source_campaign_manifest": str(manifest_path),
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "include_points": include_points,
        "include_plots": include_plots,
        "include_reports": include_reports,
        "files": copied_files,
    }
    bundle_manifest_path = bundle_dir / "bundle_manifest.json"
    write_json(bundle_manifest_path, bundle_manifest)
    zip_path = shutil.make_archive(str(bundle_dir), "zip", root_dir=bundle_dir)
    return CampaignBundlePaths(bundle_dir, bundle_manifest_path, Path(zip_path))


def run_bundle_filenames(include_points: bool, include_plots: bool, include_reports: bool) -> list[str]:
    filenames = ["metadata.json", "recipe_snapshot.yaml", "safety_snapshot.yaml"]
    if include_points:
        filenames.append("points.csv")
    if include_plots:
        filenames.extend(["iv_plot.svg", "single_gate_heatmap.svg", "ac_lockin_plot.svg", "pulse_plot.svg"])
    if include_reports:
        filenames.extend(["report.md", "single_gate_report.md", "ac_lockin_report.md", "pulse_report.md"])
    filenames.append("single_gate_stats.csv")
    return filenames


def copy_file_record(source: Path, target: Path, kind: str) -> dict[str, str]:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return {"kind": kind, "source": str(source), "target": str(target)}


def write_campaign_stats_csv(manifest_or_path: dict[str, Any] | str | Path, output_path: str | Path | None = None) -> Path:
    manifest = load_campaign_manifest(manifest_or_path)
    output = Path(output_path) if output_path is not None else campaign_output_path(manifest_or_path, "campaign_stats.csv")
    fieldnames = [
        "sample_id",
        "device_id",
        "measurement_name",
        "quality_status",
        "runs",
        "completed",
        "qc_pass",
        "qc_fail",
        "mean_fitted_resistance_ohm",
        "std_fitted_resistance_ohm",
        "relative_std_percent",
        "min_fitted_resistance_ohm",
        "max_fitted_resistance_ohm",
        "mean_points",
    ]
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in campaign_stats_rows(manifest):
            writer.writerow(row)
    return output


def campaign_stats_rows(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    runs = manifest.get("runs") or []
    groups = sorted(
        {
            (
                run.get("sample_id") or "",
                run.get("device_id") or "",
                run.get("measurement_name") or "",
                run.get("quality_status") or "n/a",
            )
            for run in runs
        }
    )
    for sample_id, device_id, measurement_name, quality_status in groups:
        group = [
            run
            for run in runs
            if (run.get("sample_id") or "") == sample_id
            and (run.get("device_id") or "") == device_id
            and (run.get("measurement_name") or "") == measurement_name
            and (run.get("quality_status") or "n/a") == quality_status
        ]
        resistances = [
            float(run["fitted_resistance_ohm"])
            for run in group
            if run.get("fitted_resistance_ohm") is not None
        ]
        points = [float(run["points"]) for run in group if run.get("points") is not None]
        mean = mean_value(resistances)
        std = sample_std(resistances)
        relative_std = None if mean in {None, 0} or std is None else abs(std / mean) * 100
        rows.append(
            {
                "sample_id": sample_id,
                "device_id": device_id,
                "measurement_name": measurement_name,
                "quality_status": quality_status,
                "runs": len(group),
                "completed": sum(1 for run in group if run.get("completed") is True),
                "qc_pass": sum(1 for run in group if (run.get("quality_status") or "n/a") == "PASS"),
                "qc_fail": sum(1 for run in group if (run.get("quality_status") or "n/a") == "FAIL"),
                "mean_fitted_resistance_ohm": mean,
                "std_fitted_resistance_ohm": std,
                "relative_std_percent": relative_std,
                "min_fitted_resistance_ohm": min(resistances) if resistances else None,
                "max_fitted_resistance_ohm": max(resistances) if resistances else None,
                "mean_points": mean_value(points),
            }
        )
    return rows


def campaign_has_fitted_resistance_values(manifest: dict[str, Any]) -> bool:
    return any(run.get("fitted_resistance_ohm") is not None for run in manifest.get("runs") or [])


def write_campaign_resistance_histogram_svg(
    manifest_or_path: dict[str, Any] | str | Path,
    output_path: str | Path | None = None,
    bins: int = 12,
) -> Path:
    manifest = load_campaign_manifest(manifest_or_path)
    output = Path(output_path) if output_path is not None else campaign_output_path(
        manifest_or_path,
        "campaign_resistance_histogram.svg",
    )
    resistances = [
        float(run["fitted_resistance_ohm"])
        for run in manifest.get("runs") or []
        if run.get("fitted_resistance_ohm") is not None
    ]
    if not resistances:
        raise ValueError("No fitted resistance values to plot.")
    bins = max(1, bins)
    r_min, r_max = min(resistances), max(resistances)
    if r_min == r_max:
        r_min -= abs(r_min) * 0.05 or 1
        r_max += abs(r_max) * 0.05 or 1
    width = (r_max - r_min) / bins
    counts = [0] * bins
    for value in resistances:
        index = min(bins - 1, int((value - r_min) / width))
        counts[index] += 1
    max_count = max(counts) or 1

    svg_width, svg_height = 820, 520
    left, right, top, bottom = 86, 36, 70, 82
    plot_w = svg_width - left - right
    plot_h = svg_height - top - bottom
    bar_gap = 4
    bar_w = plot_w / bins
    bars = []
    labels = []
    for index, count in enumerate(counts):
        h = 0 if max_count == 0 else plot_h * count / max_count
        x = left + index * bar_w
        y = top + plot_h - h
        bars.append(
            f'<rect x="{x + bar_gap / 2:.2f}" y="{y:.2f}" width="{max(1, bar_w - bar_gap):.2f}" height="{h:.2f}" fill="#0f766e" />'
        )
        if bins <= 12:
            label_value = r_min + index * width
            labels.append(
                f'<text x="{x:.2f}" y="{top + plot_h + 24}" font-family="Arial, sans-serif" font-size="11" fill="#4b5563" transform="rotate(35 {x:.2f} {top + plot_h + 24})">{label_value:.4g}</text>'
            )
    title = escape(str(manifest.get("campaign_name") or "campaign"))
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{svg_width}" height="{svg_height}" viewBox="0 0 {svg_width} {svg_height}">
  <rect width="100%" height="100%" fill="#ffffff" />
  <text x="{left}" y="30" font-family="Arial, sans-serif" font-size="18" fill="#111827">{title}</text>
  <text x="{left}" y="54" font-family="Arial, sans-serif" font-size="13" fill="#374151">fitted resistance histogram, n={len(resistances)}, range={r_min:.6g} to {r_max:.6g} ohm</text>
  <rect x="{left}" y="{top}" width="{plot_w}" height="{plot_h}" fill="#f9fafb" stroke="#9ca3af" />
  {''.join(bars)}
  {''.join(labels)}
  <text x="{left + plot_w / 2 - 76:.2f}" y="{svg_height - 20}" font-family="Arial, sans-serif" font-size="14" fill="#111827">Fitted resistance (ohm)</text>
  <text x="20" y="{top + plot_h / 2 + 34:.2f}" transform="rotate(-90 20 {top + plot_h / 2 + 34:.2f})" font-family="Arial, sans-serif" font-size="14" fill="#111827">Run count</text>
  <text x="{left - 32}" y="{top + 5}" font-family="Arial, sans-serif" font-size="12" fill="#4b5563">{max_count}</text>
  <text x="{left - 20}" y="{top + plot_h}" font-family="Arial, sans-serif" font-size="12" fill="#4b5563">0</text>
</svg>
'''
    output.write_text(svg, encoding="utf-8")
    return output


def write_campaign_report(manifest_or_path: dict[str, Any] | str | Path, output_path: str | Path | None = None) -> Path:
    manifest = load_campaign_manifest(manifest_or_path)
    output = Path(output_path) if output_path is not None else campaign_output_path(manifest_or_path, "campaign_report.md")
    output.write_text(format_campaign_report(manifest), encoding="utf-8")
    return output


def format_campaign_report(manifest: dict[str, Any]) -> str:
    counts = manifest.get("counts") or {}
    lines = [
        f"# {manifest.get('campaign_name')}",
        "",
        "## Summary",
        "",
        f"- Generated: {manifest.get('generated_at')}",
        f"- Runs: {counts.get('completed_runs', 0)}/{counts.get('runs', 0)} completed",
        f"- Failed runs: {counts.get('failed_runs', 0)}",
        f"- Interrupted runs: {counts.get('interrupted_runs', 0)}",
        f"- Batches: {counts.get('completed_batches', 0)}/{counts.get('batches', 0)} completed",
        f"- Schemes: {counts.get('completed_schemes', 0)}/{counts.get('schemes', 0)} completed",
        f"- Run QC: {format_qc_counts(counts.get('run_quality') or {})}",
        f"- Run types: {format_qc_counts(counts.get('run_types') or {})}",
        f"- Source runs: {(manifest.get('source_counts') or {}).get('runs', counts.get('runs', 0))}",
        "",
        "## Roots",
        "",
    ]
    roots = manifest.get("roots") or {}
    for key in ["raw_dir", "batch_dir", "scheme_dir"]:
        lines.append(f"- {key}: `{roots.get(key)}`")
    filter_lines = format_campaign_filters(manifest.get("filters") or {})
    if filter_lines:
        lines.extend(["", "## Filters", "", *filter_lines])
    stats_rows = campaign_stats_rows(manifest)
    if stats_rows:
        lines.extend(
            [
                "",
                "## Resistance Stats",
                "",
                "| Sample | Device | Measurement | QC | Runs | Mean R | Std R | Rel Std | Min R | Max R |",
                "|---|---|---|---|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for row in stats_rows[:30]:
            lines.append(
                (
                    f"| {row['sample_id']} | {row['device_id']} | {row['measurement_name']} | "
                    f"{row['quality_status']} | {row['runs']} | "
                    f"{fmt(row['mean_fitted_resistance_ohm'], ' ohm')} | "
                    f"{fmt(row['std_fitted_resistance_ohm'], ' ohm')} | "
                    f"{fmt(row['relative_std_percent'], ' %')} | "
                    f"{fmt(row['min_fitted_resistance_ohm'], ' ohm')} | "
                    f"{fmt(row['max_fitted_resistance_ohm'], ' ohm')} |"
                )
            )
        if len(stats_rows) > 30:
            lines.append(f"| ... | ... | ... | ... | {len(stats_rows) - 30} more groups |  |  |  |  |  |")
    lines.extend(
        [
            "",
            "## Recent Runs",
            "",
            "| # | Type | Measurement | Completed | QC | Points | Fitted R | Gate points | Gate leakage max | Sample | Device | Error | Run directory |",
            "|---:|---|---|---:|---|---:|---:|---:|---:|---|---|---|---|",
        ]
    )
    runs = list(manifest.get("runs") or [])
    for index, run in enumerate(runs[-25:], start=max(1, len(runs) - 24)):
        lines.append(
            (
                f"| {index} | {run.get('measurement_type') or 'drain_iv'} | {run.get('measurement_name') or ''} | {run.get('completed')} | "
                f"{run.get('quality_status') or 'n/a'} | {run.get('points') or run.get('points_written') or 0} | "
                f"{fmt(run.get('fitted_resistance_ohm'), ' ohm')} | {fmt(run.get('gate_points'))} | "
                f"{fmt(run.get('gate_leakage_abs_max_a'), ' A')} | {run.get('sample_id') or ''} | "
                f"{run.get('device_id') or ''} | {run.get('error_type') or ''} | `{run.get('run_dir')}` |"
            )
        )
    lines.extend(["", "## Batches", "", "| Name | Completed | QC | Runs | Summary |", "|---|---:|---|---:|---|"])
    for batch in manifest.get("batches") or []:
        lines.append(
            (
                f"| {batch.get('name')} | {batch.get('completed')} | {batch.get('quality_status') or 'n/a'} | "
                f"{batch.get('completed_runs')}/{batch.get('runs')} | `{batch.get('summary_path')}` |"
            )
        )
    lines.extend(["", "## Schemes", "", "| Name | Completed | QC | Steps | Summary |", "|---|---:|---|---:|---|"])
    for scheme in manifest.get("schemes") or []:
        lines.append(
            (
                f"| {scheme.get('name')} | {scheme.get('completed')} | {scheme.get('quality_status') or 'n/a'} | "
                f"{scheme.get('completed_steps')}/{scheme.get('steps')} | `{scheme.get('summary_path')}` |"
            )
        )
    return "\n".join(lines) + "\n"


def format_qc_counts(counts: dict[str, int]) -> str:
    if not counts:
        return "none"
    return ", ".join(f"{key}={value}" for key, value in sorted(counts.items()))


def format_campaign_filters(filters: dict[str, Any]) -> list[str]:
    lines = []
    for key, value in filters.items():
        if value in {None, False}:
            continue
        lines.append(f"- {key}: {value}")
    return lines


def load_campaign_manifest(manifest_or_path: dict[str, Any] | str | Path) -> dict[str, Any]:
    if isinstance(manifest_or_path, dict):
        return manifest_or_path
    return read_json(resolve_campaign_manifest_path(manifest_or_path))


def resolve_campaign_manifest_path(path: str | Path) -> Path:
    candidate = Path(path)
    if candidate.is_dir():
        candidate = candidate / "campaign_manifest.json"
    if not candidate.exists():
        raise FileNotFoundError(f"Missing campaign manifest: {candidate}")
    return candidate


def campaign_output_path(manifest_or_path: dict[str, Any] | str | Path, filename: str) -> Path:
    if isinstance(manifest_or_path, dict):
        return Path(filename)
    return resolve_campaign_manifest_path(manifest_or_path).with_name(filename)


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


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def write_json(path: Path, data: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, sort_keys=True, default=str)
