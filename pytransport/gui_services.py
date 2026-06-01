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

from .ac_lockin import run_ac_lockin_sweep
from .instruments.fake import CoupledFakeDeviceState, CoupledFakeSMU, FakeLockIn, FakeSMU
from .method_registry import handler_for_measurement_type
from .pulse import run_pulse_measurement
from .quality import evaluate_run_quality, quality_report_to_dict
from .recipes import load_named_safety_preset
from .run_index import append_run_index
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
