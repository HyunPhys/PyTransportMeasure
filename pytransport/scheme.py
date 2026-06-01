"""Measurement scheme recipes composed of recipe and batch steps."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .batch import format_batch_plan, load_batch, normalize_existing_path, safe_name
from .io import unique_run_dir
from .method_registry import handler_for_scheme_step
from .recipes import (
    DrainIVRecipe,
    QualityChecks,
    SingleGateRecipe,
    SweepSegment,
)


class ExperimentOverrides(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sample_id: str | None = None
    device_id: str | None = None
    operator: str | None = None
    notes: str | None = None
    tags: list[str] | None = None
    append_tags: list[str] = Field(default_factory=list)


class InstrumentOverrides(BaseModel):
    model_config = ConfigDict(extra="forbid")

    address: str | None = None
    timeout_ms: int | None = Field(default=None, gt=0)
    terminal: str | None = None
    voltage_range_v: float | None = Field(default=None, gt=0)
    current_range_a: float | None = Field(default=None, gt=0)


class SweepOverrides(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: str | None = None
    start_v: float | None = None
    stop_v: float | None = None
    points: int | None = Field(default=None, gt=1)
    delay_s: float | None = Field(default=None, ge=0.0)
    current_compliance_a: float | None = Field(default=None, gt=0)
    segments: list[SweepSegment] | None = None


class OutputOverrides(BaseModel):
    model_config = ConfigDict(extra="forbid")

    directory: Path | None = None


class RecipeOverrides(BaseModel):
    model_config = ConfigDict(extra="forbid")

    measurement_name: str | None = None
    measurement_suffix: str | None = None
    safety_preset: str | None = None
    experiment: ExperimentOverrides | None = None
    instrument: InstrumentOverrides | None = None
    sweep: SweepOverrides | None = None
    output: OutputOverrides | None = None
    checks: QualityChecks | None = None


class SchemeMatrixRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1)
    overrides: RecipeOverrides = Field(default_factory=RecipeOverrides)


class SchemeMatrix(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rows: list[SchemeMatrixRow] = Field(min_length=1)


class SchemeStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["drain_iv", "single_gate", "batch"]
    label: str | None = None
    recipe: Path | None = None
    batch: Path | None = None
    overrides: RecipeOverrides | None = None
    matrix: SchemeMatrix | None = None
    enabled: bool = True
    repeat: int = Field(default=1, ge=1)
    interval_s: float = Field(default=0.0, ge=0.0)

    @model_validator(mode="after")
    def path_matches_type(self) -> "SchemeStep":
        if self.type in {"drain_iv", "single_gate"} and self.recipe is None:
            raise ValueError(f"{self.type} steps require recipe")
        if self.type == "batch" and self.batch is None:
            raise ValueError("batch steps require batch")
        if self.type in {"drain_iv", "single_gate"} and self.batch is not None:
            raise ValueError(f"{self.type} steps cannot define batch")
        if self.type == "batch" and self.recipe is not None:
            raise ValueError("batch steps cannot define recipe")
        if self.type == "batch" and self.overrides is not None:
            raise ValueError("batch steps cannot define overrides")
        if self.type == "batch" and self.matrix is not None:
            raise ValueError("batch steps cannot define matrix")
        if self.type == "single_gate" and self.overrides is not None:
            raise ValueError("single_gate steps do not support overrides yet")
        if self.type == "single_gate" and self.matrix is not None:
            raise ValueError("single_gate steps do not support matrix yet")
        return self


class SchemeRecipe(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    stop_on_error: bool = True
    steps: list[SchemeStep] = Field(min_length=1)


@dataclass(frozen=True)
class ResolvedSchemeStep:
    index: int
    type: str
    label: str
    path: Path
    repeat_index: int
    repeat_count: int
    interval_s: float
    overrides: RecipeOverrides | None = None
    matrix_label: str | None = None
    matrix_index: int | None = None
    matrix_count: int | None = None


def load_scheme(path: str | Path) -> SchemeRecipe:
    scheme_path = Path(path)
    with scheme_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{scheme_path} must contain a YAML mapping")
    return SchemeRecipe.model_validate(data)


def resolve_scheme_steps(scheme: SchemeRecipe, scheme_path: str | Path) -> list[ResolvedSchemeStep]:
    resolved = []
    for index, step in enumerate(scheme.steps):
        if not step.enabled:
            continue
        raw_path = step.batch if step.type == "batch" else step.recipe
        assert raw_path is not None
        path = resolve_scheme_path(raw_path, scheme_path)
        base_label = step.label or path.stem
        matrix_rows = step.matrix.rows if step.matrix is not None else [None]
        for matrix_index, row in enumerate(matrix_rows, start=1):
            matrix_label = None if row is None else row.label
            row_overrides = None if row is None else row.overrides
            overrides = merge_recipe_overrides(step.overrides, row_overrides)
            row_base_label = base_label if row is None else f"{base_label}_{row.label}"
            for repeat_index in range(1, step.repeat + 1):
                label = row_base_label if step.repeat == 1 else f"{row_base_label}_rep{repeat_index:02d}"
                resolved.append(
                    ResolvedSchemeStep(
                        index=index,
                        type=step.type,
                        label=label,
                        path=path,
                        repeat_index=repeat_index,
                        repeat_count=step.repeat,
                        interval_s=step.interval_s,
                        overrides=overrides,
                        matrix_label=matrix_label,
                        matrix_index=None if row is None else matrix_index,
                        matrix_count=None if row is None else len(matrix_rows),
                    )
                )
    return resolved


def resolve_scheme_path(path: Path, scheme_path: str | Path) -> Path:
    if path.is_absolute():
        return path
    relative_to_scheme = Path(scheme_path).parent / path
    if relative_to_scheme.exists():
        return normalize_existing_path(relative_to_scheme)
    return path


def format_scheme_plan(
    scheme: SchemeRecipe,
    scheme_path: str | Path,
    safety_dir: str | Path = "configs/safety",
    preview_points: int = 3,
) -> str:
    steps = resolve_scheme_steps(scheme, scheme_path)
    lines = [
        "Scheme plan",
        f"Scheme: {scheme.name}",
        f"Scheme file: {Path(scheme_path)}",
        f"Enabled steps: {len(steps)}",
        f"Step entries: {sum(1 for step in scheme.steps if step.enabled)}",
        f"Stop on error: {scheme.stop_on_error}",
    ]
    for number, step in enumerate(steps, start=1):
        lines.extend(["", f"=== Step {number}/{len(steps)}: {step.label} ({step.type}) ==="])
        if step.type == "drain_iv":
            recipe = load_scheme_step_recipe(step)
            lines.append(handler_for_scheme_step(step.type).format_plan(recipe, step.path, safety_dir, preview_points))
            if step.overrides is not None:
                lines.extend(["", "Overrides", *format_recipe_overrides(step.overrides)])
        elif step.type == "single_gate":
            recipe = load_scheme_step_single_gate_recipe(step)
            lines.append(handler_for_scheme_step(step.type).format_plan(recipe, step.path, safety_dir, preview_points))
        else:
            lines.append(format_batch_plan(load_batch(step.path), step.path, safety_dir, preview_points))
    return "\n".join(lines)


def load_scheme_step_recipe(step: ResolvedSchemeStep) -> DrainIVRecipe:
    recipe = handler_for_scheme_step("drain_iv").load_recipe(step.path)
    if step.overrides is None:
        return recipe
    return apply_recipe_overrides(recipe, step.overrides)


def load_scheme_step_single_gate_recipe(step: ResolvedSchemeStep) -> SingleGateRecipe:
    return handler_for_scheme_step("single_gate").load_recipe(step.path)


def apply_recipe_overrides(recipe: DrainIVRecipe, overrides: RecipeOverrides) -> DrainIVRecipe:
    data = recipe.model_dump(mode="json")
    update = overrides.model_dump(mode="json", exclude_none=True)
    measurement_suffix = update.pop("measurement_suffix", None)
    experiment_update = update.get("experiment")
    append_tags = []
    if isinstance(experiment_update, dict):
        append_tags = experiment_update.pop("append_tags", []) or []
        if not experiment_update:
            update.pop("experiment", None)
    deep_update(data, update)
    if measurement_suffix:
        data["measurement_name"] = f"{data['measurement_name']}{measurement_suffix}"
    if append_tags:
        current_tags = list(data.get("experiment", {}).get("tags") or [])
        for tag in append_tags:
            if tag not in current_tags:
                current_tags.append(tag)
        data.setdefault("experiment", {})["tags"] = current_tags
    return DrainIVRecipe.model_validate(data)


def merge_recipe_overrides(
    base: RecipeOverrides | None,
    overlay: RecipeOverrides | None,
) -> RecipeOverrides | None:
    if base is None:
        return overlay
    if overlay is None:
        return base
    data = base.model_dump(mode="json", exclude_none=True)
    update = overlay.model_dump(mode="json", exclude_none=True)
    base_append_tags = []
    overlay_append_tags = []
    base_experiment = data.get("experiment")
    overlay_experiment = update.get("experiment")
    if isinstance(base_experiment, dict):
        base_append_tags = list(base_experiment.get("append_tags") or [])
    if isinstance(overlay_experiment, dict):
        overlay_append_tags = list(overlay_experiment.get("append_tags") or [])
    deep_update(data, update)
    merged_append_tags = base_append_tags[:]
    for tag in overlay_append_tags:
        if tag not in merged_append_tags:
            merged_append_tags.append(tag)
    if merged_append_tags:
        data.setdefault("experiment", {})["append_tags"] = merged_append_tags
    return RecipeOverrides.model_validate(data)


def deep_update(target: dict[str, Any], update: dict[str, Any]) -> None:
    for key, value in update.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            deep_update(target[key], value)
        else:
            target[key] = value


def format_recipe_overrides(overrides: RecipeOverrides) -> list[str]:
    data = overrides.model_dump(mode="json", exclude_none=True)
    lines: list[str] = []
    flatten_mapping(data, lines)
    return [f"- {line}" for line in lines] or ["- none"]


def flatten_mapping(data: dict[str, Any], lines: list[str], prefix: str = "") -> None:
    for key, value in data.items():
        name = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            flatten_mapping(value, lines, name)
        else:
            lines.append(f"{name}: {value}")


def create_scheme_summary(
    scheme: SchemeRecipe,
    scheme_path: str | Path,
    dry_run: bool,
    output_dir: str | Path = "data/schemes",
) -> tuple[Path, dict[str, Any]]:
    started_at = datetime.now().isoformat(timespec="seconds")
    scheme_dir = unique_run_dir(Path(output_dir), f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{safe_name(scheme.name)}")
    scheme_dir.mkdir(parents=True, exist_ok=False)
    summary = {
        "scheme_name": scheme.name,
        "scheme_path": str(Path(scheme_path)),
        "started_at": started_at,
        "finished_at": None,
        "dry_run": dry_run,
        "stop_on_error": scheme.stop_on_error,
        "completed": False,
        "steps": [],
    }
    return scheme_dir, summary


def finish_scheme_summary(path: Path, summary: dict[str, Any]) -> Path:
    summary["finished_at"] = datetime.now().isoformat(timespec="seconds")
    steps = summary.get("steps") or []
    summary["completed"] = bool(steps) and all(step.get("completed") for step in steps)
    output_path = path / "scheme_summary.json"
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2, sort_keys=True, default=str)
    return output_path
