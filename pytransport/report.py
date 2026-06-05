"""Markdown report generation for saved runs."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .inspect import format_sweep, read_run_metadata
from .summary import summarize_run


def write_run_report(run_dir: str | Path, output_path: str | Path | None = None) -> Path:
    path = Path(run_dir)
    output = Path(output_path) if output_path is not None else path / "report.md"
    output.write_text(format_run_report(path), encoding="utf-8")
    return output


def format_run_report(run_dir: str | Path) -> str:
    path = Path(run_dir)
    metadata = read_run_metadata(path)
    summary = summarize_run(path)
    recipe = metadata.get("recipe") or {}
    safety = metadata.get("safety") or {}
    quality = metadata.get("quality") or {}
    experiment = recipe.get("experiment") or {}
    instrument = recipe.get("instrument") or {}
    sweep = recipe.get("sweep") or {}
    files = file_status(path)

    lines = [
        f"# {metadata.get('measurement_name') or path.name}",
        "",
        "## Summary",
        "",
        f"- Run directory: `{path}`",
        f"- Started: {metadata.get('started_at') or 'n/a'}",
        f"- Finished: {metadata.get('finished_at') or 'n/a'}",
        f"- Completed: {metadata.get('completed')}",
        f"- Interrupted: {metadata.get('interrupted')}",
        f"- Points: {summary.points}",
        f"- Voltage range: {fmt(summary.voltage_min_v, ' V')} to {fmt(summary.voltage_max_v, ' V')}",
        f"- Current range: {fmt(summary.current_min_a, ' A')} to {fmt(summary.current_max_a, ' A')}",
        f"- Fitted resistance: {fmt(summary.fitted_resistance_ohm, ' ohm')}",
        "",
        "## Experiment",
        "",
        f"- Sample: {experiment.get('sample_id') or 'n/a'}",
        f"- Device: {experiment.get('device_id') or 'n/a'}",
        f"- Cooldown: {experiment.get('cooldown_id') or 'n/a'}",
        f"- Contact geometry: {experiment.get('contact_geometry') or 'n/a'}",
        f"- Contact notes: {experiment.get('contact_notes') or 'n/a'}",
        f"- Lab notebook: {experiment.get('lab_notebook_ref') or 'n/a'}",
        f"- Operator: {experiment.get('operator') or 'n/a'}",
        f"- Tags: {', '.join(experiment.get('tags') or []) or 'none'}",
        f"- Notes: {experiment.get('notes') or 'n/a'}",
        "",
        "## Recipe",
        "",
        f"- Recipe path: `{metadata.get('recipe_path') or 'n/a'}`",
        f"- Safety preset: {recipe.get('safety_preset') or 'n/a'}",
        f"- Instrument: {instrument.get('id') or 'n/a'} @ `{instrument.get('address') or 'n/a'}`",
        f"- Terminal: {instrument.get('terminal') or 'n/a'}",
        f"- Voltage range: {fmt(instrument.get('voltage_range_v'), ' V')}",
        f"- Current range: {fmt(instrument.get('current_range_a'), ' A')}",
        f"- NPLC: {fmt(instrument.get('nplc'), '')}",
        f"- Sweep: {format_sweep(sweep)}",
        f"- Current compliance: {fmt(sweep.get('current_compliance_a'), ' A')}",
        "",
        "## Safety",
        "",
        f"- Safety preset name: {safety.get('name') or 'n/a'}",
        f"- Max abs voltage: {fmt(safety.get('max_abs_voltage_v'), ' V')}",
        f"- Max abs current: {fmt(safety.get('max_abs_current_a'), ' A')}",
        f"- Default compliance: {fmt(safety.get('default_current_compliance_a'), ' A')}",
        "",
        "## Files",
        "",
    ]
    for label, exists in files.items():
        lines.append(f"- {label}: {'yes' if exists else 'no'}")

    if quality:
        lines.extend(["", "## Quality", "", f"- Status: {quality.get('status') or 'n/a'}"])
        for result in quality.get("results") or []:
            lines.append(
                f"- {result.get('name')}: {'PASS' if result.get('passed') else 'FAIL'} - {result.get('message')}"
            )

    if (path / "iv_plot.svg").exists():
        lines.extend(["", "## Plot", "", "![I-V plot](iv_plot.svg)"])

    if metadata.get("error_type"):
        lines.extend(
            [
                "",
                "## Error",
                "",
                f"- Type: {metadata.get('error_type')}",
                f"- Message: {metadata.get('error_message')}",
                f"- Triggered limit: {metadata.get('triggered_limit') or 'n/a'}",
            ]
        )

    return "\n".join(lines) + "\n"


def file_status(run_dir: Path) -> dict[str, bool]:
    return {
        "points.csv": (run_dir / "points.csv").exists(),
        "metadata.json": (run_dir / "metadata.json").exists(),
        "recipe_snapshot.yaml": (run_dir / "recipe_snapshot.yaml").exists(),
        "safety_snapshot.yaml": (run_dir / "safety_snapshot.yaml").exists(),
        "iv_plot.svg": (run_dir / "iv_plot.svg").exists(),
    }


def fmt(value: Any, unit: str = "") -> str:
    if value is None:
        return "n/a"
    if isinstance(value, int | float):
        return f"{value:.6g}{unit}"
    return f"{value}{unit}"
