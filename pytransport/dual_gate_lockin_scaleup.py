"""Helpers for preparing broader dual-gate lock-in candidate recipes."""

from __future__ import annotations

from pathlib import Path

import yaml

from .dual_gate_lockin import (
    dual_gate_lockin_chunks,
    dual_gate_lockin_point_count,
    format_dual_gate_lockin_chunk_plan,
    format_dual_gate_lockin_plan,
)
from .dual_gate_lockin_review import (
    audit_dual_gate_lockin_run,
    audit_dual_gate_lockin_scale_up,
    format_dual_gate_lockin_acceptance,
    format_dual_gate_lockin_scale_up_audit,
    format_scale_up_blocking_acceptance_issues,
    read_dual_gate_lockin_metadata,
    scale_up_blocking_acceptance_issues,
)
from .measurement_parameters import missing_required_smu_hardware_parameters
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


def format_dual_gate_lockin_broader_scan_packet(
    accepted_run_dir: str | Path,
    candidate_recipe_path: str | Path,
    recipe: DualGateLockInRecipe,
    safety: SafetyPreset,
    *,
    chunk_size: int,
    max_hardware_points: int,
) -> str:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if max_hardware_points <= 0:
        raise ValueError("max_hardware_points must be positive")

    point_count = dual_gate_lockin_point_count(recipe)
    chunks = dual_gate_lockin_chunks(recipe, chunk_size)
    chunk_plan = format_dual_gate_lockin_chunk_plan(
        recipe,
        candidate_recipe_path,
        chunk_size=chunk_size,
        max_hardware_points=max_hardware_points,
    )
    acceptance = audit_dual_gate_lockin_run(accepted_run_dir, require_lockin_settings=True)
    blocking_warnings = scale_up_blocking_acceptance_issues(acceptance)
    scale_up = audit_dual_gate_lockin_scale_up(accepted_run_dir, recipe)
    measurement_parameter_issues = missing_required_smu_hardware_parameters(recipe, roles=("gate1", "gate2"))
    ready = (
        acceptance.accepted
        and not blocking_warnings
        and scale_up.compatible
        and not measurement_parameter_issues
        and all(chunk.point_count <= max_hardware_points for chunk in chunks)
    )

    lines = [
        "# Dual-Gate Lock-In Broader Scan Packet",
        "",
        f"- Accepted previous run: `{accepted_run_dir}`",
        f"- Candidate recipe: `{candidate_recipe_path}`",
        f"- Measurement name: `{recipe.measurement_name}`",
        f"- Candidate grid: {recipe.gate1_sweep.points} x {recipe.gate2_sweep.points} = {point_count} points",
        f"- Chunk size: {chunk_size}",
        f"- Chunks: {len(chunks)}",
        f"- Max hardware points per invocation: {max_hardware_points}",
        f"- Packet ready for lab execution: {'yes' if ready else 'no'}",
        "",
        "## Measurement Parameters",
        "",
        "| Role | Address | Terminal | Voltage range (V) | Current range (A) | NPLC | Source delay (s) | Sweep | Compliance (A) |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | --- | ---: |",
        _smu_parameter_row("gate1", recipe.gate1_instrument, recipe.gate1_sweep),
        _smu_parameter_row("gate2", recipe.gate2_instrument, recipe.gate2_sweep),
        "",
        f"- Safety preset: `{safety.name}`",
        f"- Safety max abs voltage: {safety.max_abs_voltage_v:.6g} V",
        f"- Safety max abs current: {safety.max_abs_current_a:.6g} A",
        f"- Lock-in address: `{recipe.lockin.address}`",
        f"- Lock-in reference frequency: {_fmt_optional(recipe.lockin.reference_frequency_hz)} Hz",
        f"- Lock-in sine output amplitude: {_fmt_optional(recipe.lockin.sine_output_amplitude_v)} V",
        f"- Lock-in time constant index: {_fmt_optional(recipe.lockin.time_constant_index)}",
        f"- Lock-in settle time constants: {recipe.lockin.settle_time_constants:.6g}",
        "",
    ]
    if measurement_parameter_issues:
        lines.extend(
            [
                "## Blocking Measurement-Parameter Issues",
                "",
                *[
                    f"- `{issue.role}.{issue.parameter}`: {issue.message}"
                    for issue in measurement_parameter_issues
                ],
                "",
            ]
        )

    lines.extend(
        [
            "## Accepted-Run Audit",
            "",
            "```text",
            format_dual_gate_lockin_acceptance(acceptance),
            "```",
            "",
        ]
    )
    if blocking_warnings:
        lines.extend(
            [
                "## Scale-Up Blocking Warnings",
                "",
                "```text",
                format_scale_up_blocking_acceptance_issues(blocking_warnings),
                "```",
                "",
            ]
        )
    lines.extend(
        [
            "## Candidate Compatibility",
            "",
            "```text",
            format_dual_gate_lockin_scale_up_audit(scale_up),
            "```",
            "",
            "## Hardware-Free Commands",
            "",
            "```powershell",
            f"ptm dual-gate-lockin-scale-up-check {accepted_run_dir} {candidate_recipe_path}",
            f"ptm dual-gate-lockin-preflight {candidate_recipe_path}",
            f"ptm dual-gate-lockin-chunk-plan {candidate_recipe_path} --chunk-size {chunk_size} --max-hardware-points {max_hardware_points}",
            "```",
            "",
            "## Chunk Acquisition Commands",
            "",
            "Run one chunk, inspect the partial run folder, then continue with the next command.",
            "",
            "```powershell",
            *[
                line
                for chunk in chunks
                for line in _chunk_command_block(candidate_recipe_path, accepted_run_dir, chunk, max_hardware_points)
            ],
            _chunk_feedback_command(recipe.measurement_name, len(chunks)),
            "```",
            "",
            "## After Acquisition",
            "",
            "```powershell",
            _stitch_command(recipe.measurement_name, len(chunks)),
            f"ptm dual-gate-lockin-audit data\\raw\\<{recipe.measurement_name}_stitched> --write-report",
            "```",
            "",
            "## Embedded Chunk Plan",
            "",
            "```text",
            chunk_plan,
            "```",
            "",
            "## Lab Checklist",
            "",
            "- [ ] `Packet ready for lab execution` says `yes`.",
            "- [ ] Gate1/Gate2 NPLC, voltage range, current range, and compliance are intentional.",
            "- [ ] SR860 preflight readback matches the recipe.",
            "- [ ] The first chunk is run with the smallest practical point count.",
            "- [ ] After each chunk, gate outputs are off and leakage remains comfortably below compliance.",
            "- [ ] The stitched run passes strict `dual-gate-lockin-audit` before further expansion.",
            "",
        ]
    )
    return "\n".join(lines)


def write_dual_gate_lockin_broader_scan_packet(
    output_path: str | Path,
    accepted_run_dir: str | Path,
    candidate_recipe_path: str | Path,
    recipe: DualGateLockInRecipe,
    safety: SafetyPreset,
    *,
    chunk_size: int,
    max_hardware_points: int,
    overwrite: bool = False,
) -> Path:
    path = Path(output_path)
    if path.exists() and not overwrite:
        raise FileExistsError(f"Broader scan packet already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        format_dual_gate_lockin_broader_scan_packet(
            accepted_run_dir,
            candidate_recipe_path,
            recipe,
            safety,
            chunk_size=chunk_size,
            max_hardware_points=max_hardware_points,
        ),
        encoding="utf-8",
    )
    return path


def _smu_parameter_row(role: str, instrument, sweep) -> str:
    sweep_text = f"{sweep.start_v:.6g} -> {sweep.stop_v:.6g} V, {sweep.points} points, settle {sweep.settle_s:.6g} s"
    return (
        f"| {role} | `{instrument.address}` | {_fmt_optional(instrument.terminal)} | "
        f"{_fmt_optional(instrument.voltage_range_v)} | {_fmt_optional(instrument.current_range_a)} | "
        f"{_fmt_optional(instrument.nplc)} | {_fmt_optional(instrument.source_delay_s)} | "
        f"{sweep_text} | {sweep.current_compliance_a:.6g} |"
    )


def _chunk_command(recipe_path: str | Path, accepted_run_dir: str | Path, chunk, max_hardware_points: int) -> str:
    resume = "" if chunk.chunk_number == 1 else f" --resume-from-run data\\raw\\<chunk_{chunk.chunk_number - 1:02d}_run_folder>"
    return (
        f"ptm dual-gate-lockin {recipe_path} --allow-active-sweep{resume} "
        f"--stop-after-new-points {chunk.point_count} --max-hardware-points {max_hardware_points} "
        f'--hardware-approval-note "accepted previous run; chunk {chunk.chunk_number}" '
        f"--accepted-previous-run {accepted_run_dir} --yes --progress --plot --report --gate-stats"
    )


def _chunk_command_block(
    recipe_path: str | Path,
    accepted_run_dir: str | Path,
    chunk,
    max_hardware_points: int,
) -> tuple[str, str]:
    return (
        _chunk_command(recipe_path, accepted_run_dir, chunk, max_hardware_points),
        f"ptm dual-gate-lockin-chunk-audit data\\raw\\<chunk_{chunk.chunk_number:02d}_run_folder>",
    )


def _stitch_command(measurement_name: str, chunk_count: int) -> str:
    placeholders = " ".join(
        f"data\\raw\\<{measurement_name}_chunk_{index:02d}>"
        for index in range(1, chunk_count + 1)
    )
    return (
        f"ptm dual-gate-lockin-stitch-chunks {placeholders} "
        f"--measurement-name {measurement_name}_stitched --gate-stats --plot --report"
    )


def _chunk_feedback_command(measurement_name: str, chunk_count: int) -> str:
    placeholders = " ".join(
        f"data\\raw\\<{measurement_name}_chunk_{index:02d}>"
        for index in range(1, chunk_count + 1)
    )
    return f"ptm dual-gate-lockin-chunk-feedback {placeholders} --output docs\\<{measurement_name}_chunk_feedback.md>"


def _fmt_optional(value) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)
