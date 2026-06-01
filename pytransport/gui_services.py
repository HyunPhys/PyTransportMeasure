"""Core services used by the desktop GUI.

This module intentionally has no PySide dependency. The GUI calls these helpers
so measurement logic remains shared with the CLI and testable without opening a
window.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import yaml

from .ac_lockin import run_ac_lockin_sweep
from .inspect import read_run_metadata
from .instruments.fake import CoupledFakeDeviceState, CoupledFakeSMU, FakeLockIn, FakeSMU
from .method_registry import handler_for_measurement_type
from .pulse import run_pulse_measurement
from .quality import evaluate_run_quality, quality_report_to_dict
from .recipes import load_named_safety_preset
from .run_index import append_run_index, read_run_index
from .runner import run_drain_iv
from .single_gate import run_single_gate_sweep
from .single_gate_review import write_single_gate_stats_csv


GuiMethod = Literal["drain_iv", "single_gate_sweep", "ac_lockin_sweep", "pulse_measurement"]


@dataclass(frozen=True)
class GuiFakeSettings:
    resistance_ohm: float = 1_000_000.0
    noise_std_a: float = 0.0
    channel_resistance_ohm: float = 1_000_000.0
    gate_leak_resistance_ohm: float = 1_000_000_000.0
    gate_modulation_per_v: float = 0.0
    lockin_r_v: float = 1e-6
    lockin_phase_deg: float = 0.0
    lockin_noise_std_v: float = 0.0


@dataclass(frozen=True)
class GuiRunResult:
    metadata: dict[str, Any]
    summary_text: str
    quality_text: str
    artifact_paths: dict[str, str] = field(default_factory=dict)

    @property
    def run_dir(self) -> Path:
        return Path(str(self.metadata["run_dir"]))


def available_gui_methods() -> dict[str, str]:
    return {
        "drain_iv": "Drain I-V",
        "single_gate_sweep": "Single-gate sweep",
        "ac_lockin_sweep": "AC lock-in sweep",
        "pulse_measurement": "Pulse measurement",
    }


def default_recipe_path(measurement_type: GuiMethod) -> Path:
    paths = {
        "drain_iv": Path("configs/recipes/drain_iv_1k_resistor.yaml"),
        "single_gate_sweep": Path("configs/recipes/single_gate_dry_run.yaml"),
        "ac_lockin_sweep": Path("configs/recipes/ac_lockin_dry_run.yaml"),
        "pulse_measurement": Path("configs/recipes/pulse_dry_run.yaml"),
    }
    return paths[measurement_type]


def load_recipe_text(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8")


def default_recipe_text(measurement_type: GuiMethod) -> str:
    return load_recipe_text(default_recipe_path(measurement_type))


def validate_recipe_text(
    measurement_type: GuiMethod,
    text: str,
    safety_dir: str | Path = "configs/safety",
    preview_points: int = 5,
) -> tuple[bool, str]:
    try:
        data = yaml.safe_load(text)
        if not isinstance(data, dict):
            raise ValueError("recipe YAML must contain a mapping")
        handler = handler_for_measurement_type(measurement_type)
        recipe = recipe_from_mapping(measurement_type, data)
        safety = load_named_safety_preset(recipe.safety_preset, safety_dir)
        plan = handler.format_plan(recipe, "<editor>", safety_dir, preview_points)
        return True, "\n".join(["Validation: PASS", f"Safety preset: {safety.name}", "", plan])
    except Exception as exc:
        return False, f"Validation: FAIL\n{type(exc).__name__}: {exc}"


def save_recipe_text(
    measurement_type: GuiMethod,
    text: str,
    path: str | Path,
    safety_dir: str | Path = "configs/safety",
) -> Path:
    ok, message = validate_recipe_text(measurement_type, text, safety_dir)
    if not ok:
        raise ValueError(message)
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text, encoding="utf-8")
    return output


def recipe_from_mapping(measurement_type: GuiMethod, data: dict[str, Any]) -> Any:
    handler = handler_for_measurement_type(measurement_type)
    # Reuse each method loader's underlying Pydantic model without writing a
    # temporary file.
    model = type(handler.load_recipe(default_recipe_path(measurement_type)))
    return model.model_validate(data)


def format_gui_plan(
    measurement_type: GuiMethod,
    recipe_path: str | Path,
    safety_dir: str | Path = "configs/safety",
    preview_points: int = 5,
) -> str:
    handler = handler_for_measurement_type(measurement_type)
    recipe = handler.load_recipe(recipe_path)
    return handler.format_plan(recipe, recipe_path, safety_dir, preview_points)


def run_gui_dry_run(
    measurement_type: GuiMethod,
    recipe_path: str | Path,
    safety_dir: str | Path = "configs/safety",
    fake: GuiFakeSettings | None = None,
    index_path: str | Path = "data/run_index.jsonl",
    create_plot: bool = True,
    create_report: bool = True,
) -> GuiRunResult:
    fake_settings = fake or GuiFakeSettings()
    handler = handler_for_measurement_type(measurement_type)
    recipe = handler.load_recipe(recipe_path)
    safety = load_named_safety_preset(recipe.safety_preset, safety_dir)

    if measurement_type == "drain_iv":
        metadata = run_drain_iv(
            recipe,
            safety,
            FakeSMU(fake_settings.resistance_ohm, fake_settings.noise_std_a),
            recipe_path=recipe_path,
        )
    elif measurement_type == "single_gate_sweep":
        state = CoupledFakeDeviceState(
            channel_resistance_ohm=fake_settings.channel_resistance_ohm,
            gate_leak_resistance_ohm=fake_settings.gate_leak_resistance_ohm,
            gate_modulation_per_v=fake_settings.gate_modulation_per_v,
            noise_std_a=fake_settings.noise_std_a,
        )
        metadata = run_single_gate_sweep(
            recipe,
            safety,
            CoupledFakeSMU("drain", state),
            CoupledFakeSMU("gate", state),
            recipe_path=recipe_path,
        )
    elif measurement_type == "ac_lockin_sweep":
        metadata = run_ac_lockin_sweep(
            recipe,
            safety,
            FakeSMU(fake_settings.resistance_ohm, fake_settings.noise_std_a),
            FakeLockIn(
                signal_r_v=fake_settings.lockin_r_v,
                phase_deg=fake_settings.lockin_phase_deg,
                noise_std_v=fake_settings.lockin_noise_std_v,
            ),
            recipe_path=recipe_path,
        )
    elif measurement_type == "pulse_measurement":
        metadata = run_pulse_measurement(
            recipe,
            safety,
            FakeSMU(fake_settings.resistance_ohm, fake_settings.noise_std_a),
            recipe_path=recipe_path,
            sleep=False,
        )
    else:
        raise ValueError(f"Unsupported GUI method: {measurement_type}")

    metadata.setdefault("measurement_type", measurement_type)
    run_dir = Path(metadata["run_dir"])
    artifact_paths: dict[str, str] = {}
    if create_plot and metadata["points_written"] > 0:
        plot_path = handler.write_plot(run_dir, None)
        artifact_paths["plot_path"] = str(plot_path)
        metadata[path_metadata_key(handler.plot_filename)] = str(plot_path)
    if measurement_type == "single_gate_sweep" and metadata["points_written"] > 0:
        stats_path = write_single_gate_stats_csv(run_dir)
        artifact_paths["single_gate_stats_path"] = str(stats_path)
        metadata["single_gate_stats_path"] = str(stats_path)
    if create_report and metadata["points_written"] > 0:
        report_path = handler.write_report(run_dir, None)
        artifact_paths["report_path"] = str(report_path)
        metadata[path_metadata_key(handler.report_filename)] = str(report_path)

    quality_report = evaluate_run_quality(run_dir)
    metadata["quality"] = quality_report_to_dict(quality_report)
    write_metadata(metadata)
    append_run_index(metadata, index_path)
    summary_text = handler.format_summary(handler.summarize(run_dir)) if metadata["points_written"] > 0 else ""
    return GuiRunResult(
        metadata=metadata,
        summary_text=summary_text,
        quality_text=format_gui_quality(quality_report),
        artifact_paths=artifact_paths,
    )


def list_gui_runs(index_path: str | Path = "data/run_index.jsonl", limit: int = 100) -> list[dict[str, Any]]:
    records = read_run_index(index_path)
    return list(reversed(records[-limit:]))


def load_gui_saved_run(run_dir: str | Path) -> GuiRunResult:
    metadata = read_run_metadata(run_dir)
    handler = handler_for_measurement_type(str(metadata.get("measurement_type") or "drain_iv"))
    summary_text = ""
    if Path(run_dir, "points.csv").exists():
        summary_text = handler.format_summary(handler.summarize(run_dir))
    quality = metadata.get("quality") or {}
    quality_text = f"Quality: {quality.get('status') or 'n/a'}"
    for result in quality.get("results") or []:
        mark = "PASS" if result.get("passed") else "FAIL"
        quality_text += f"\n- {result.get('name')}: {mark} ({result.get('message')})"
    return GuiRunResult(
        metadata=metadata,
        summary_text=summary_text,
        quality_text=quality_text,
        artifact_paths=artifact_paths_from_metadata(metadata),
    )


def artifact_paths_from_metadata(metadata: dict[str, Any]) -> dict[str, str]:
    paths = {}
    for key in [
        "plot_path",
        "report_path",
        "single_gate_heatmap_path",
        "single_gate_report_path",
        "single_gate_stats_path",
        "ac_lockin_plot_path",
        "ac_lockin_report_path",
        "pulse_plot_path",
        "pulse_report_path",
    ]:
        value = metadata.get(key)
        if value:
            paths[key] = str(value)
    return paths


def path_metadata_key(filename: str) -> str:
    return {
        "iv_plot.svg": "plot_path",
        "report.md": "report_path",
        "single_gate_heatmap.svg": "single_gate_heatmap_path",
        "single_gate_report.md": "single_gate_report_path",
        "ac_lockin_plot.svg": "ac_lockin_plot_path",
        "ac_lockin_report.md": "ac_lockin_report_path",
        "pulse_plot.svg": "pulse_plot_path",
        "pulse_report.md": "pulse_report_path",
    }.get(filename, f"{Path(filename).stem}_path")


def write_metadata(metadata: dict[str, Any]) -> None:
    metadata_path = Path(str(metadata["metadata_path"]))
    with metadata_path.open("w", encoding="utf-8") as handle:
        json.dump(metadata, handle, indent=2, sort_keys=True, default=str)


def format_gui_quality(report) -> str:
    lines = [f"Quality: {report.status}"]
    for result in report.results:
        mark = "PASS" if result.passed else "FAIL"
        lines.append(f"- {result.name}: {mark} ({result.message})")
    return "\n".join(lines)
