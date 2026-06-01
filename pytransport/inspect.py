"""Inspect saved run folders."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .method_registry import handler_for_metadata, measurement_type_from_metadata


def read_run_metadata(run_dir: str | Path) -> dict[str, Any]:
    metadata_path = Path(run_dir) / "metadata.json"
    if not metadata_path.exists():
        raise FileNotFoundError(f"Missing metadata: {metadata_path}")
    with metadata_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{metadata_path} must contain a JSON object")
    return data


def inspect_run(run_dir: str | Path) -> str:
    path = Path(run_dir)
    metadata = read_run_metadata(path)
    measurement_type = measurement_type_from_metadata(metadata)
    handler = handler_for_metadata(metadata)
    recipe = metadata.get("recipe") or {}
    experiment = recipe.get("experiment") or {}
    instrument = recipe.get("instrument") or recipe.get("drain_instrument") or recipe.get("source_instrument") or {}
    sweep = recipe.get("sweep") or recipe.get("drain_sweep") or recipe.get("bias_sweep") or {}
    pulse = recipe.get("pulse") or {}
    files = {filename: path / filename for filename in handler.artifact_filenames()}
    summary_text = handler.format_summary(handler.summarize(path))

    lines = [
        "Run inspection",
        f"Run: {path}",
        f"Measurement type: {measurement_type}",
        "",
        summary_text,
        "",
        "Experiment",
        f"Sample: {experiment.get('sample_id') or 'n/a'}",
        f"Device: {experiment.get('device_id') or 'n/a'}",
        f"Operator: {experiment.get('operator') or 'n/a'}",
        f"Tags: {', '.join(experiment.get('tags') or []) or 'none'}",
        f"Notes: {experiment.get('notes') or 'n/a'}",
        "",
        "Recipe",
        f"Recipe path: {metadata.get('recipe_path') or 'n/a'}",
        f"Safety preset: {recipe.get('safety_preset') or 'n/a'}",
        f"Instrument: {instrument.get('id') or 'n/a'} @ {instrument.get('address') or 'n/a'}",
        f"Terminal: {instrument.get('terminal') or 'n/a'}",
        f"Sweep: {format_sweep(sweep) if sweep else 'n/a'}",
    ]
    if measurement_type == "single_gate_sweep":
        gate_instrument = recipe.get("gate_instrument") or {}
        gate_sweep = recipe.get("gate_sweep") or {}
        lines.extend(
            [
                f"Gate instrument: {gate_instrument.get('id') or 'n/a'} @ {gate_instrument.get('address') or 'n/a'}",
                f"Gate sweep: {format_gate_sweep(gate_sweep)}",
            ]
        )
    if measurement_type == "ac_lockin_sweep":
        lockin = recipe.get("lockin") or {}
        lines.extend(
            [
                f"Lock-in: {lockin.get('id') or 'n/a'} @ {lockin.get('address') or 'n/a'}",
                f"Lock-in channels: {', '.join(lockin.get('channels') or []) or 'n/a'}",
                f"Lock-in timing: {lockin.get('read_timing') or 'n/a'}",
            ]
        )
    if measurement_type == "pulse_measurement":
        lines.append(f"Pulse: {format_pulse(pulse)}")
    lines.extend(["", "Files"])
    for label, file_path in files.items():
        lines.append(f"{label}: {'yes' if file_path.exists() else 'no'} ({file_path})")
    return "\n".join(lines)


def format_sweep(sweep: dict[str, Any]) -> str:
    mode = sweep.get("mode") or "linear_one_way"
    if mode == "multi_segment":
        segments = sweep.get("segments") or []
        return f"multi_segment, {len(segments)} segments"
    return f"{mode}, {sweep.get('start_v')} V to {sweep.get('stop_v')} V, {sweep.get('points')} base points"


def format_gate_sweep(sweep: dict[str, Any]) -> str:
    return (
        f"{sweep.get('start_v')} V to {sweep.get('stop_v')} V, "
        f"{sweep.get('points')} points, settle {sweep.get('settle_s')} s"
    )


def format_pulse(pulse: dict[str, Any]) -> str:
    return (
        f"base {pulse.get('base_v')} V, pulse {pulse.get('amplitude_v')} V, "
        f"width {pulse.get('width_s')} s, period {pulse.get('period_s')} s, "
        f"count {pulse.get('count')}, acquisition {pulse.get('acquisition') or 'n/a'}"
    )
