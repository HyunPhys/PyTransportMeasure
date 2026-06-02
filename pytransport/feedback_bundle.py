"""Portable feedback bundles for lab laptop run results."""

from __future__ import annotations

import json
import platform
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .inspect import inspect_run, read_run_metadata
from .method_registry import handler_for_metadata, measurement_type_from_metadata
from .quality import evaluate_run_quality, format_quality_report, quality_report_to_dict


@dataclass(frozen=True)
class FeedbackBundlePaths:
    bundle_dir: Path
    manifest_path: Path
    zip_path: Path


def create_feedback_bundle(
    run_dir: str | Path,
    output_dir: str | Path = "data/feedback",
    include_points: bool = True,
    include_plots: bool = True,
    include_reports: bool = True,
    extra_files: list[str | Path] | None = None,
) -> FeedbackBundlePaths:
    source_run_dir = Path(run_dir)
    metadata = read_run_metadata(source_run_dir)
    bundle_dir = unique_feedback_dir(Path(output_dir), source_run_dir, metadata)
    bundle_dir.mkdir(parents=True, exist_ok=False)

    copied_files = copy_run_files(
        source_run_dir,
        bundle_dir / "run",
        metadata,
        include_points=include_points,
        include_plots=include_plots,
        include_reports=include_reports,
    )
    inspection_path = bundle_dir / "inspection.txt"
    inspection_path.write_text(inspect_run(source_run_dir), encoding="utf-8")
    environment_path = bundle_dir / "environment.json"
    environment = collect_environment(metadata)
    environment_path.write_text(json.dumps(environment, indent=2, sort_keys=True), encoding="utf-8")
    quality_path = bundle_dir / "quality.txt"
    quality_report = evaluate_run_quality(source_run_dir)
    quality_path.write_text(format_quality_report(quality_report), encoding="utf-8")
    extra_records = copy_extra_files(extra_files or [], bundle_dir / "extras")

    manifest = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "source_run_dir": str(source_run_dir),
        "measurement_type": measurement_type_from_metadata(metadata),
        "measurement_name": metadata.get("measurement_name"),
        "completed": metadata.get("completed"),
        "error_type": metadata.get("error_type"),
        "error_message": metadata.get("error_message"),
        "points_written": metadata.get("points_written"),
        "quality": quality_report_to_dict(quality_report),
        "included": {
            "points": include_points,
            "plots": include_plots,
            "reports": include_reports,
        },
        "files": copied_files
        + [
            {"kind": "inspection", "path": inspection_path.relative_to(bundle_dir).as_posix()},
            {"kind": "environment", "path": environment_path.relative_to(bundle_dir).as_posix()},
            {"kind": "quality", "path": quality_path.relative_to(bundle_dir).as_posix()},
        ]
        + extra_records,
    }
    manifest_path = bundle_dir / "bundle_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True, default=str), encoding="utf-8")
    zip_path = Path(shutil.make_archive(str(bundle_dir), "zip", root_dir=bundle_dir))
    return FeedbackBundlePaths(bundle_dir=bundle_dir, manifest_path=manifest_path, zip_path=zip_path)


def copy_extra_files(extra_files: list[str | Path], target_extra_dir: Path) -> list[dict[str, str]]:
    copied: list[dict[str, str]] = []
    for source_value in extra_files:
        source = Path(source_value)
        if not source.exists() or not source.is_file():
            raise FileNotFoundError(f"Extra feedback file does not exist: {source}")
        target_extra_dir.mkdir(parents=True, exist_ok=True)
        target = unique_target_path(target_extra_dir, source.name)
        shutil.copy2(source, target)
        copied.append(
            {
                "kind": "extra",
                "source": str(source),
                "path": target.relative_to(target_extra_dir.parent).as_posix(),
            }
        )
    return copied


def copy_run_files(
    source_run_dir: Path,
    target_run_dir: Path,
    metadata: dict[str, Any],
    include_points: bool,
    include_plots: bool,
    include_reports: bool,
) -> list[dict[str, str]]:
    target_run_dir.mkdir(parents=True, exist_ok=False)
    copied: list[dict[str, str]] = []
    for filename in feedback_filenames(metadata, include_points, include_plots, include_reports):
        source = source_run_dir / filename
        if not source.exists():
            continue
        target = target_run_dir / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        copied.append({"kind": "run", "path": target.relative_to(target_run_dir.parent).as_posix()})
    return copied


def feedback_filenames(
    metadata: dict[str, Any],
    include_points: bool,
    include_plots: bool,
    include_reports: bool,
) -> list[str]:
    handler = handler_for_metadata(metadata)
    filenames = ["metadata.json", "recipe_snapshot.yaml", "safety_snapshot.yaml"]
    if include_points:
        filenames.append("points.csv")
    optional_files = list(handler.extra_artifact_filenames)
    if include_plots:
        optional_files.append(handler.plot_filename)
    if include_reports:
        optional_files.append(handler.report_filename)
    for filename in optional_files:
        if filename in filenames:
            continue
        filenames.append(filename)
    return filenames


def collect_environment(metadata: dict[str, Any]) -> dict[str, Any]:
    return {
        "python": sys.version,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "measurement_type": measurement_type_from_metadata(metadata),
        "instrument_idn": metadata.get("instrument_idn"),
        "instrument_probe": metadata.get("instrument_probe")
        or metadata.get("drain_instrument_probe")
        or metadata.get("source_instrument_probe"),
    }


def unique_feedback_dir(output_dir: Path, run_dir: Path, metadata: dict[str, Any]) -> Path:
    measurement_name = str(metadata.get("measurement_name") or run_dir.name)
    base = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{safe_name(measurement_name)}_feedback"
    candidate = output_dir / base
    if not candidate.exists():
        return candidate
    for suffix in range(2, 1000):
        candidate = output_dir / f"{base}_{suffix:02d}"
        if not candidate.exists():
            return candidate
    raise FileExistsError(f"Could not create a unique feedback bundle directory for {measurement_name}")


def unique_target_path(directory: Path, filename: str) -> Path:
    candidate = directory / safe_name(filename)
    if not candidate.exists():
        return candidate
    stem = candidate.stem
    suffix = candidate.suffix
    for index in range(2, 1000):
        next_candidate = directory / f"{stem}_{index:02d}{suffix}"
        if not next_candidate.exists():
            return next_candidate
    raise FileExistsError(f"Could not create a unique feedback extra filename for {filename}")


def safe_name(value: str) -> str:
    cleaned = "".join(char if char.isalnum() or char in {"-", "_", "."} else "_" for char in value.strip())
    return cleaned.strip("_") or "run"
