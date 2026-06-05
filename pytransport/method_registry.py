"""Measurement method registry for saved-run dispatch."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

SummaryFn = Callable[[str | Path], Any]
FormatSummaryFn = Callable[[Any], str]
WriteArtifactFn = Callable[[str | Path, str | Path | None], Path]
SummaryFieldsFn = Callable[[Any], dict[str, Any]]
RecipeLoaderFn = Callable[[str | Path], Any]
PlanFormatterFn = Callable[[Any, str | Path, str | Path, int], str]


@dataclass(frozen=True)
class MethodHandler:
    measurement_type: str
    scheme_step_type: str
    display_name: str
    plot_filename: str
    report_filename: str
    extra_artifact_filenames: tuple[str, ...]
    summarize: SummaryFn
    format_summary: FormatSummaryFn
    write_plot: WriteArtifactFn
    write_report: WriteArtifactFn
    campaign_summary_fields: SummaryFieldsFn
    load_recipe: RecipeLoaderFn
    format_plan: PlanFormatterFn

    def artifact_filenames(self) -> tuple[str, ...]:
        common = ("points.csv", "metadata.json", "recipe_snapshot.yaml", "safety_snapshot.yaml")
        return common + (self.plot_filename, self.report_filename) + self.extra_artifact_filenames


def drain_iv_campaign_summary_fields(summary: Any) -> dict[str, Any]:
    return {
        "points": summary.points,
        "fitted_resistance_ohm": summary.fitted_resistance_ohm,
        "voltage_min_v": summary.voltage_min_v,
        "voltage_max_v": summary.voltage_max_v,
        "current_min_a": summary.current_min_a,
        "current_max_a": summary.current_max_a,
    }


def single_gate_campaign_summary_fields(summary: Any) -> dict[str, Any]:
    return {
        "points": summary.points,
        "gate_points": summary.gate_points,
        "drain_points": summary.drain_points,
        "gate_voltage_min_v": summary.gate_voltage_min_v,
        "gate_voltage_max_v": summary.gate_voltage_max_v,
        "drain_voltage_min_v": summary.drain_voltage_min_v,
        "drain_voltage_max_v": summary.drain_voltage_max_v,
        "drain_current_min_a": summary.drain_current_min_a,
        "drain_current_max_a": summary.drain_current_max_a,
        "gate_current_min_a": summary.gate_current_min_a,
        "gate_current_max_a": summary.gate_current_max_a,
        "gate_leakage_abs_max_a": summary.gate_leakage_abs_max_a,
        "voltage_min_v": summary.drain_voltage_min_v,
        "voltage_max_v": summary.drain_voltage_max_v,
        "current_min_a": summary.drain_current_min_a,
        "current_max_a": summary.drain_current_max_a,
    }


def dual_gate_campaign_summary_fields(summary: Any) -> dict[str, Any]:
    return {
        "points": summary.points,
        "gate1_points": summary.gate1_points,
        "gate2_points": summary.gate2_points,
        "drain_points": summary.drain_points,
        "gate1_voltage_min_v": summary.gate1_voltage_min_v,
        "gate1_voltage_max_v": summary.gate1_voltage_max_v,
        "gate2_voltage_min_v": summary.gate2_voltage_min_v,
        "gate2_voltage_max_v": summary.gate2_voltage_max_v,
        "drain_voltage_min_v": summary.drain_voltage_min_v,
        "drain_voltage_max_v": summary.drain_voltage_max_v,
        "drain_current_min_a": summary.drain_current_min_a,
        "drain_current_max_a": summary.drain_current_max_a,
        "gate1_leakage_abs_max_a": summary.gate1_leakage_abs_max_a,
        "gate2_leakage_abs_max_a": summary.gate2_leakage_abs_max_a,
        "voltage_min_v": summary.drain_voltage_min_v,
        "voltage_max_v": summary.drain_voltage_max_v,
        "current_min_a": summary.drain_current_min_a,
        "current_max_a": summary.drain_current_max_a,
    }


def ac_lockin_campaign_summary_fields(summary: Any) -> dict[str, Any]:
    return {
        "points": summary.points,
        "voltage_min_v": summary.bias_min_v,
        "voltage_max_v": summary.bias_max_v,
        "current_min_a": summary.source_current_min_a,
        "current_max_a": summary.source_current_max_a,
        "lockin_r_min_v": summary.lockin_r_min_v,
        "lockin_r_max_v": summary.lockin_r_max_v,
        "lockin_theta_min_deg": summary.lockin_theta_min_deg,
        "lockin_theta_max_deg": summary.lockin_theta_max_deg,
    }


def pulse_campaign_summary_fields(summary: Any) -> dict[str, Any]:
    return {
        "points": summary.points,
        "voltage_min_v": summary.pulse_voltage_v,
        "voltage_max_v": summary.pulse_voltage_v,
        "current_min_a": summary.current_min_a,
        "current_max_a": summary.current_max_a,
        "pulse_voltage_v": summary.pulse_voltage_v,
        "pulse_width_s": summary.width_s,
        "pulse_period_s": summary.period_s,
        "pulse_duty_cycle": summary.duty_cycle,
    }


def summarize_drain_iv(run_dir: str | Path) -> Any:
    from .summary import summarize_run

    return summarize_run(run_dir)


def format_drain_iv_summary(summary: Any) -> str:
    from .summary import format_summary

    return format_summary(summary)


def write_drain_iv_plot(run_dir: str | Path, output_path: str | Path | None = None) -> Path:
    from .plot import write_iv_svg

    return write_iv_svg(run_dir, output_path)


def write_drain_iv_report(run_dir: str | Path, output_path: str | Path | None = None) -> Path:
    from .report import write_run_report

    return write_run_report(run_dir, output_path)


def summarize_single_gate(run_dir: str | Path) -> Any:
    from .single_gate_review import summarize_single_gate_run

    return summarize_single_gate_run(run_dir)


def format_single_gate(summary: Any) -> str:
    from .single_gate_review import format_single_gate_summary

    return format_single_gate_summary(summary)


def write_single_gate_plot(run_dir: str | Path, output_path: str | Path | None = None) -> Path:
    from .single_gate_review import write_single_gate_heatmap_svg

    return write_single_gate_heatmap_svg(run_dir, output_path)


def write_single_gate_method_report(run_dir: str | Path, output_path: str | Path | None = None) -> Path:
    from .single_gate_review import write_single_gate_report

    return write_single_gate_report(run_dir, output_path)


def summarize_dual_gate(run_dir: str | Path) -> Any:
    from .dual_gate_review import summarize_dual_gate_run

    return summarize_dual_gate_run(run_dir)


def format_dual_gate(summary: Any) -> str:
    from .dual_gate_review import format_dual_gate_summary

    return format_dual_gate_summary(summary)


def write_dual_gate_plot(run_dir: str | Path, output_path: str | Path | None = None) -> Path:
    from .dual_gate_review import write_dual_gate_heatmap_svg

    return write_dual_gate_heatmap_svg(run_dir, output_path)


def write_dual_gate_method_report(run_dir: str | Path, output_path: str | Path | None = None) -> Path:
    from .dual_gate_review import write_dual_gate_report

    return write_dual_gate_report(run_dir, output_path)


def summarize_ac_lockin(run_dir: str | Path) -> Any:
    from .ac_lockin_review import summarize_ac_lockin_run

    return summarize_ac_lockin_run(run_dir)


def format_ac_lockin_method_summary(summary: Any) -> str:
    from .ac_lockin_review import format_ac_lockin_summary

    return format_ac_lockin_summary(summary)


def write_ac_lockin_method_plot(run_dir: str | Path, output_path: str | Path | None = None) -> Path:
    from .ac_lockin_review import write_ac_lockin_plot_svg

    return write_ac_lockin_plot_svg(run_dir, output_path)


def write_ac_lockin_method_report(run_dir: str | Path, output_path: str | Path | None = None) -> Path:
    from .ac_lockin_review import write_ac_lockin_report

    return write_ac_lockin_report(run_dir, output_path)


def summarize_pulse(run_dir: str | Path) -> Any:
    from .pulse_review import summarize_pulse_run

    return summarize_pulse_run(run_dir)


def format_pulse_method_summary(summary: Any) -> str:
    from .pulse_review import format_pulse_summary

    return format_pulse_summary(summary)


def write_pulse_method_plot(run_dir: str | Path, output_path: str | Path | None = None) -> Path:
    from .pulse_review import write_pulse_plot_svg

    return write_pulse_plot_svg(run_dir, output_path)


def write_pulse_method_report(run_dir: str | Path, output_path: str | Path | None = None) -> Path:
    from .pulse_review import write_pulse_report

    return write_pulse_report(run_dir, output_path)


def load_drain_iv_recipe(recipe_path: str | Path) -> Any:
    from .recipes import load_recipe

    return load_recipe(recipe_path)


def load_single_gate_method_recipe(recipe_path: str | Path) -> Any:
    from .recipes import load_single_gate_recipe

    return load_single_gate_recipe(recipe_path)


def load_dual_gate_method_recipe(recipe_path: str | Path) -> Any:
    from .recipes import load_dual_gate_recipe

    return load_dual_gate_recipe(recipe_path)


def load_ac_lockin_method_recipe(recipe_path: str | Path) -> Any:
    from .recipes import load_ac_lockin_recipe

    return load_ac_lockin_recipe(recipe_path)


def load_pulse_method_recipe(recipe_path: str | Path) -> Any:
    from .recipes import load_pulse_recipe

    return load_pulse_recipe(recipe_path)


def format_drain_iv_plan(recipe: Any, recipe_path: str | Path, safety_dir: str | Path, preview_points: int) -> str:
    from .plan import build_measurement_plan_from_objects, format_measurement_plan
    from .recipes import load_named_safety_preset

    safety = load_named_safety_preset(recipe.safety_preset, safety_dir)
    return format_measurement_plan(build_measurement_plan_from_objects(recipe, safety, recipe_path, preview_points))


def format_single_gate_method_plan(recipe: Any, recipe_path: str | Path, safety_dir: str | Path, preview_points: int) -> str:
    from .recipes import load_named_safety_preset
    from .single_gate import format_single_gate_plan

    safety = load_named_safety_preset(recipe.safety_preset, safety_dir)
    return format_single_gate_plan(recipe, safety, recipe_path, preview_points)


def format_dual_gate_method_plan(recipe: Any, recipe_path: str | Path, safety_dir: str | Path, preview_points: int) -> str:
    from .dual_gate import format_dual_gate_plan
    from .recipes import load_named_safety_preset

    safety = load_named_safety_preset(recipe.safety_preset, safety_dir)
    return format_dual_gate_plan(recipe, safety, recipe_path, preview_points)


def format_ac_lockin_method_plan(recipe: Any, recipe_path: str | Path, safety_dir: str | Path, preview_points: int) -> str:
    from .ac_lockin import format_ac_lockin_plan
    from .recipes import load_named_safety_preset

    safety = load_named_safety_preset(recipe.safety_preset, safety_dir)
    return format_ac_lockin_plan(recipe, safety, recipe_path, preview_points)


def format_pulse_method_plan(recipe: Any, recipe_path: str | Path, safety_dir: str | Path, preview_points: int) -> str:
    from .pulse import format_pulse_plan
    from .recipes import load_named_safety_preset

    safety = load_named_safety_preset(recipe.safety_preset, safety_dir)
    return format_pulse_plan(recipe, safety, recipe_path, preview_points)


METHOD_HANDLERS: dict[str, MethodHandler] = {
    "drain_iv": MethodHandler(
        measurement_type="drain_iv",
        scheme_step_type="drain_iv",
        display_name="Drain I-V",
        plot_filename="iv_plot.svg",
        report_filename="report.md",
        extra_artifact_filenames=(),
        summarize=summarize_drain_iv,
        format_summary=format_drain_iv_summary,
        write_plot=write_drain_iv_plot,
        write_report=write_drain_iv_report,
        campaign_summary_fields=drain_iv_campaign_summary_fields,
        load_recipe=load_drain_iv_recipe,
        format_plan=format_drain_iv_plan,
    ),
    "single_gate_sweep": MethodHandler(
        measurement_type="single_gate_sweep",
        scheme_step_type="single_gate",
        display_name="Single-gate sweep",
        plot_filename="single_gate_heatmap.svg",
        report_filename="single_gate_report.md",
        extra_artifact_filenames=("single_gate_stats.csv",),
        summarize=summarize_single_gate,
        format_summary=format_single_gate,
        write_plot=write_single_gate_plot,
        write_report=write_single_gate_method_report,
        campaign_summary_fields=single_gate_campaign_summary_fields,
        load_recipe=load_single_gate_method_recipe,
        format_plan=format_single_gate_method_plan,
    ),
    "dual_gate_sweep": MethodHandler(
        measurement_type="dual_gate_sweep",
        scheme_step_type="dual_gate",
        display_name="Dual-gate sweep",
        plot_filename="dual_gate_heatmap.svg",
        report_filename="dual_gate_report.md",
        extra_artifact_filenames=("dual_gate_stats.csv",),
        summarize=summarize_dual_gate,
        format_summary=format_dual_gate,
        write_plot=write_dual_gate_plot,
        write_report=write_dual_gate_method_report,
        campaign_summary_fields=dual_gate_campaign_summary_fields,
        load_recipe=load_dual_gate_method_recipe,
        format_plan=format_dual_gate_method_plan,
    ),
    "ac_lockin_sweep": MethodHandler(
        measurement_type="ac_lockin_sweep",
        scheme_step_type="ac_lockin",
        display_name="AC lock-in sweep",
        plot_filename="ac_lockin_plot.svg",
        report_filename="ac_lockin_report.md",
        extra_artifact_filenames=(),
        summarize=summarize_ac_lockin,
        format_summary=format_ac_lockin_method_summary,
        write_plot=write_ac_lockin_method_plot,
        write_report=write_ac_lockin_method_report,
        campaign_summary_fields=ac_lockin_campaign_summary_fields,
        load_recipe=load_ac_lockin_method_recipe,
        format_plan=format_ac_lockin_method_plan,
    ),
    "pulse_measurement": MethodHandler(
        measurement_type="pulse_measurement",
        scheme_step_type="pulse",
        display_name="Pulse measurement",
        plot_filename="pulse_plot.svg",
        report_filename="pulse_report.md",
        extra_artifact_filenames=(),
        summarize=summarize_pulse,
        format_summary=format_pulse_method_summary,
        write_plot=write_pulse_method_plot,
        write_report=write_pulse_method_report,
        campaign_summary_fields=pulse_campaign_summary_fields,
        load_recipe=load_pulse_method_recipe,
        format_plan=format_pulse_method_plan,
    ),
}

SCHEME_STEP_TO_MEASUREMENT_TYPE = {
    handler.scheme_step_type: measurement_type for measurement_type, handler in METHOD_HANDLERS.items()
}


def known_measurement_types() -> tuple[str, ...]:
    return tuple(METHOD_HANDLERS)


def measurement_type_from_metadata(metadata: dict[str, Any]) -> str:
    return str(metadata.get("measurement_type") or "drain_iv")


def measurement_type_for_scheme_step(step_type: str | None) -> str:
    return SCHEME_STEP_TO_MEASUREMENT_TYPE.get(step_type or "drain_iv", "drain_iv")


def handler_for_measurement_type(measurement_type: str | None) -> MethodHandler:
    key = measurement_type or "drain_iv"
    try:
        return METHOD_HANDLERS[key]
    except KeyError as exc:
        known = ", ".join(known_measurement_types())
        raise ValueError(f"Unsupported measurement_type {key!r}; known types: {known}") from exc


def handler_for_metadata(metadata: dict[str, Any]) -> MethodHandler:
    return handler_for_measurement_type(measurement_type_from_metadata(metadata))


def handler_for_scheme_step(step_type: str | None) -> MethodHandler:
    return handler_for_measurement_type(measurement_type_for_scheme_step(step_type))
