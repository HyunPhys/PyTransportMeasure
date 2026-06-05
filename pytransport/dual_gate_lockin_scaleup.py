"""Helpers for preparing broader dual-gate lock-in candidate recipes."""

from __future__ import annotations

from pathlib import Path

import yaml

from .dual_gate_lockin_review import read_dual_gate_lockin_metadata
from .recipes import DualGateLockInRecipe


def build_dual_gate_lockin_scale_up_recipe_data(
    accepted_run_dir: str | Path,
    gate1_start_v: float,
    gate1_stop_v: float,
    gate1_points: int,
    gate2_start_v: float,
    gate2_stop_v: float,
    gate2_points: int,
    measurement_name: str | None = None,
    output_directory: str | Path | None = None,
) -> dict:
    metadata = read_dual_gate_lockin_metadata(accepted_run_dir)
    recipe = metadata.get("recipe")
    if not isinstance(recipe, dict):
        raise ValueError(f"{accepted_run_dir} metadata does not contain a recipe snapshot")
    candidate = dict(recipe)
    candidate["gate1_sweep"] = {
        **dict(candidate.get("gate1_sweep") or {}),
        "start_v": gate1_start_v,
        "stop_v": gate1_stop_v,
        "points": gate1_points,
    }
    candidate["gate2_sweep"] = {
        **dict(candidate.get("gate2_sweep") or {}),
        "start_v": gate2_start_v,
        "stop_v": gate2_stop_v,
        "points": gate2_points,
    }
    if measurement_name is not None:
        candidate["measurement_name"] = measurement_name
    else:
        candidate["measurement_name"] = f"{candidate.get('measurement_name', 'dual_gate_lockin')}_scale_up"
    if output_directory is not None:
        candidate["output"] = {**dict(candidate.get("output") or {}), "directory": str(output_directory)}
    DualGateLockInRecipe.model_validate(candidate)
    return candidate


def write_dual_gate_lockin_scale_up_recipe(
    accepted_run_dir: str | Path,
    output_path: str | Path,
    gate1_start_v: float,
    gate1_stop_v: float,
    gate1_points: int,
    gate2_start_v: float,
    gate2_stop_v: float,
    gate2_points: int,
    measurement_name: str | None = None,
    output_directory: str | Path | None = None,
    overwrite: bool = False,
) -> Path:
    path = Path(output_path)
    if path.exists() and not overwrite:
        raise FileExistsError(f"Recipe already exists: {path}")
    data = build_dual_gate_lockin_scale_up_recipe_data(
        accepted_run_dir,
        gate1_start_v,
        gate1_stop_v,
        gate1_points,
        gate2_start_v,
        gate2_stop_v,
        gate2_points,
        measurement_name=measurement_name,
        output_directory=output_directory,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, sort_keys=False)
    return path
