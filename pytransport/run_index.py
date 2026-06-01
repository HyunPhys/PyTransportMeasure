"""Append-only run index for finding recent measurements."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DEFAULT_INDEX_PATH = Path("data/run_index.jsonl")


def build_index_record(metadata: dict[str, Any]) -> dict[str, Any]:
    recipe = metadata.get("recipe") or {}
    experiment = recipe.get("experiment") or {}
    return {
        "started_at": metadata.get("started_at"),
        "finished_at": metadata.get("finished_at"),
        "measurement_name": metadata.get("measurement_name"),
        "measurement_type": metadata.get("measurement_type") or "drain_iv",
        "completed": metadata.get("completed"),
        "interrupted": metadata.get("interrupted"),
        "error_type": metadata.get("error_type"),
        "points_written": metadata.get("points_written"),
        "run_dir": metadata.get("run_dir"),
        "metadata_path": metadata.get("metadata_path"),
        "csv_path": metadata.get("csv_path"),
        "plot_path": metadata.get("plot_path"),
        "report_path": metadata.get("report_path"),
        "single_gate_heatmap_path": metadata.get("single_gate_heatmap_path"),
        "single_gate_report_path": metadata.get("single_gate_report_path"),
        "single_gate_stats_path": metadata.get("single_gate_stats_path"),
        "ac_lockin_plot_path": metadata.get("ac_lockin_plot_path"),
        "ac_lockin_report_path": metadata.get("ac_lockin_report_path"),
        "pulse_plot_path": metadata.get("pulse_plot_path"),
        "pulse_report_path": metadata.get("pulse_report_path"),
        "recipe_path": metadata.get("recipe_path"),
        "sample_id": experiment.get("sample_id"),
        "device_id": experiment.get("device_id"),
        "tags": experiment.get("tags") or [],
    }


def append_run_index(metadata: dict[str, Any], index_path: str | Path = DEFAULT_INDEX_PATH) -> Path:
    path = Path(index_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    record = build_index_record(metadata)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True, default=str))
        handle.write("\n")
    return path


def rebuild_run_index(
    raw_dir: str | Path = "data/raw",
    index_path: str | Path = DEFAULT_INDEX_PATH,
) -> tuple[Path, int]:
    raw_path = Path(raw_dir)
    index = Path(index_path)
    index.parent.mkdir(parents=True, exist_ok=True)
    records = []
    for metadata_path in sorted(raw_path.glob("*/metadata.json")):
        with metadata_path.open("r", encoding="utf-8") as handle:
            metadata = json.load(handle)
        if not isinstance(metadata, dict):
            continue
        records.append(build_index_record(metadata))
    records.sort(key=lambda record: record.get("started_at") or "")
    with index.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True, default=str))
            handle.write("\n")
    return index, len(records)


def read_run_index(index_path: str | Path = DEFAULT_INDEX_PATH) -> list[dict[str, Any]]:
    path = Path(index_path)
    if not path.exists():
        return []
    records = []
    with path.open("r", encoding="utf-8-sig") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))
    return records


def filter_run_index(
    records: list[dict[str, Any]],
    sample_id: str | None = None,
    device_id: str | None = None,
    tag: str | None = None,
    measurement_type: str | None = None,
    completed: bool | None = None,
    failed: bool = False,
    interrupted: bool | None = None,
) -> list[dict[str, Any]]:
    filtered = []
    for record in records:
        if sample_id is not None and record.get("sample_id") != sample_id:
            continue
        if device_id is not None and record.get("device_id") != device_id:
            continue
        if tag is not None and tag not in (record.get("tags") or []):
            continue
        if measurement_type is not None and (record.get("measurement_type") or "drain_iv") != measurement_type:
            continue
        if completed is not None and record.get("completed") is not completed:
            continue
        if failed and not record.get("error_type"):
            continue
        if interrupted is not None and record.get("interrupted") is not interrupted:
            continue
        filtered.append(record)
    return filtered


def format_run_index(records: list[dict[str, Any]], limit: int = 10) -> str:
    if not records:
        return "No indexed runs found."
    selected = records[-limit:]
    lines = []
    for record in reversed(selected):
        completed = record.get("completed")
        points = record.get("points_written")
        measurement_type = record.get("measurement_type") or "drain_iv"
        sample = record.get("sample_id") or "n/a"
        device = record.get("device_id") or "n/a"
        tags = ", ".join(record.get("tags") or []) or "none"
        error = record.get("error_type") or ""
        suffix = f", error={error}" if error else ""
        lines.append(
            (
                f"{record.get('started_at')} | type={measurement_type} | completed={completed} | "
                f"points={points} | sample={sample} | device={device} | tags={tags}{suffix}\n"
                f"  {record.get('run_dir')}"
            )
        )
    return "\n".join(lines)
