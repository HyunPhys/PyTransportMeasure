"""Batch/session recipes for running multiple Drain I-V recipes."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field

from .io import unique_run_dir
from .plan import build_measurement_plan, format_measurement_plan


class BatchEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recipe: Path
    label: str | None = None
    enabled: bool = True
    repeat: int = Field(default=1, ge=1)
    interval_s: float = Field(default=0.0, ge=0.0)


class BatchQualityChecks(BaseModel):
    model_config = ConfigDict(extra="forbid")

    require_all_completed: bool = True
    require_all_run_quality_pass: bool = False
    max_relative_std_percent: float | None = Field(default=None, ge=0.0)


class BatchRecipe(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    stop_on_error: bool = True
    checks: BatchQualityChecks | None = None
    recipes: list[BatchEntry] = Field(min_length=1)


@dataclass(frozen=True)
class ResolvedBatchEntry:
    index: int
    recipe_path: Path
    label: str
    base_label: str
    repeat_index: int
    repeat_count: int
    interval_s: float


def load_batch(path: str | Path) -> BatchRecipe:
    batch_path = Path(path)
    with batch_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{batch_path} must contain a YAML mapping")
    return BatchRecipe.model_validate(data)


def resolve_batch_entries(batch: BatchRecipe, batch_path: str | Path) -> list[ResolvedBatchEntry]:
    resolved = []
    for index, entry in enumerate(batch.recipes):
        if not entry.enabled:
            continue
        recipe_path = resolve_recipe_path(entry.recipe, batch_path)
        base_label = entry.label or recipe_path.stem
        for repeat_index in range(1, entry.repeat + 1):
            label = base_label if entry.repeat == 1 else f"{base_label}_rep{repeat_index:02d}"
            resolved.append(
                ResolvedBatchEntry(
                    index=index,
                    recipe_path=recipe_path,
                    label=label,
                    base_label=base_label,
                    repeat_index=repeat_index,
                    repeat_count=entry.repeat,
                    interval_s=entry.interval_s,
                )
            )
    return resolved


def resolve_recipe_path(recipe_path: Path, batch_path: str | Path) -> Path:
    if recipe_path.is_absolute():
        return recipe_path
    relative_to_batch = Path(batch_path).parent / recipe_path
    if relative_to_batch.exists():
        return normalize_existing_path(relative_to_batch)
    return recipe_path


def normalize_existing_path(path: Path) -> Path:
    resolved = path.resolve()
    try:
        return resolved.relative_to(Path.cwd().resolve())
    except ValueError:
        return resolved


def format_batch_plan(
    batch: BatchRecipe,
    batch_path: str | Path,
    safety_dir: str | Path = "configs/safety",
    preview_points: int = 3,
) -> str:
    entries = resolve_batch_entries(batch, batch_path)
    lines = [
        "Batch plan",
        f"Batch: {batch.name}",
        f"Batch file: {Path(batch_path)}",
        f"Enabled recipes: {len(entries)}",
        f"Recipe entries: {sum(1 for entry in batch.recipes if entry.enabled)}",
        f"Stop on error: {batch.stop_on_error}",
    ]
    for number, entry in enumerate(entries, start=1):
        lines.extend(
            [
                "",
                f"=== Recipe {number}/{len(entries)}: {entry.label} ===",
                format_measurement_plan(build_measurement_plan(entry.recipe_path, safety_dir, preview_points)),
            ]
        )
    return "\n".join(lines)


def create_batch_summary(
    batch: BatchRecipe,
    batch_path: str | Path,
    dry_run: bool,
    output_dir: str | Path = "data/batches",
) -> tuple[Path, dict[str, Any]]:
    started_at = datetime.now().isoformat(timespec="seconds")
    run_dir = unique_run_dir(Path(output_dir), f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{safe_name(batch.name)}")
    run_dir.mkdir(parents=True, exist_ok=False)
    summary = {
        "batch_name": batch.name,
        "batch_path": str(Path(batch_path)),
        "started_at": started_at,
        "finished_at": None,
        "dry_run": dry_run,
        "stop_on_error": batch.stop_on_error,
        "checks": batch.checks.model_dump(mode="json") if batch.checks is not None else None,
        "quality": None,
        "completed": False,
        "runs": [],
    }
    return run_dir, summary


def finish_batch_summary(path: Path, summary: dict[str, Any]) -> Path:
    summary["finished_at"] = datetime.now().isoformat(timespec="seconds")
    runs = summary.get("runs") or []
    summary["completed"] = bool(runs) and all(run.get("completed") for run in runs)
    output_path = path / "batch_summary.json"
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2, sort_keys=True, default=str)
    return output_path


def safe_name(name: str) -> str:
    cleaned = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in name.strip())
    return cleaned or "batch"
