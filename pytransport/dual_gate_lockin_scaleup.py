"""Helpers for preparing broader dual-gate lock-in candidate recipes."""

from __future__ import annotations

from pathlib import Path

import yaml

from .dual_gate_lockin import dual_gate_lockin_point_count, format_dual_gate_lockin_plan
from .dual_gate_lockin_review import read_dual_gate_lockin_metadata
from .recipes import DualGateLockInRecipe, SafetyPreset


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


def default_dual_gate_lockin_scale_up_review_path(recipe_path: str | Path) -> Path:
    return Path(recipe_path).with_suffix(".review.md")


def format_dual_gate_lockin_scale_up_review(
    accepted_run_dir: str | Path,
    candidate_recipe_path: str | Path,
    recipe: DualGateLockInRecipe,
    safety: SafetyPreset,
    max_hardware_points: int | None = None,
) -> str:
    point_count = dual_gate_lockin_point_count(recipe)
    requested_points = point_count if max_hardware_points is None else max_hardware_points
    plan = format_dual_gate_lockin_plan(recipe, safety, candidate_recipe_path, preview_points=5)
    approval_note = "<brief lab note, e.g. 2x2 accepted; expanding to candidate grid>"
    hardware_command = (
        f"ptm dual-gate-lockin {candidate_recipe_path} --allow-active-sweep "
        f"--max-hardware-points {requested_points} "
        f'--hardware-approval-note "{approval_note}" '
        f"--accepted-previous-run {accepted_run_dir} --progress --plot --report --gate-stats"
    )
    return "\n".join(
        [
            "# Dual-Gate Lock-In Scale-Up Review",
            "",
            f"- Accepted previous run: `{accepted_run_dir}`",
            f"- Candidate recipe: `{candidate_recipe_path}`",
            f"- Candidate points: {point_count}",
            f"- Suggested `--max-hardware-points`: {requested_points}",
            "",
            "## Hardware-Free Checks",
            "",
            "```powershell",
            f"ptm dual-gate-lockin-scale-up-check {accepted_run_dir} {candidate_recipe_path}",
            "ptm dual-gate-lockin-preflight " + str(candidate_recipe_path),
            "```",
            "",
            "## Hardware Run Command",
            "",
            "Edit the approval note before running on the lab laptop.",
            "",
            "```powershell",
            hardware_command,
            "```",
            "",
            "## Candidate Plan",
            "",
            "```text",
            plan,
            "```",
            "",
            "## Lab Checklist",
            "",
            "- [ ] Accepted previous run audit passes without scale-up-blocking warnings.",
            "- [ ] Candidate grid contains every accepted previous gate point.",
            "- [ ] SR860 setting readback matches the recipe in preflight.",
            "- [ ] Runtime metadata later shows `lockin_settings_readback_matched: true`.",
            "- [ ] Gate leakage margin remains comfortable before expanding again.",
            "",
        ]
    )


def write_dual_gate_lockin_scale_up_review(
    review_path: str | Path,
    accepted_run_dir: str | Path,
    candidate_recipe_path: str | Path,
    recipe: DualGateLockInRecipe,
    safety: SafetyPreset,
    max_hardware_points: int | None = None,
    overwrite: bool = False,
) -> Path:
    path = Path(review_path)
    if path.exists() and not overwrite:
        raise FileExistsError(f"Review file already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    text = format_dual_gate_lockin_scale_up_review(
        accepted_run_dir,
        candidate_recipe_path,
        recipe,
        safety,
        max_hardware_points=max_hardware_points,
    )
    path.write_text(text, encoding="utf-8")
    return path
