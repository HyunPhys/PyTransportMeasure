"""Human-readable measurement plans before running hardware."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .recipes import DrainIVRecipe, SafetyPreset, load_named_safety_preset, load_recipe, sweep_delays, sweep_voltages
from .safety import validate_recipe_against_safety


@dataclass(frozen=True)
class PlannedPoint:
    index: int
    voltage_v: float
    delay_s: float


@dataclass(frozen=True)
class MeasurementPlan:
    recipe_path: Path
    measurement_name: str
    sample_id: str | None
    device_id: str | None
    operator: str | None
    tags: list[str]
    safety_preset: str
    address: str
    terminal: str | None
    voltage_range_v: float | None
    current_range_a: float | None
    nplc: float | None
    output_directory: Path
    sweep_mode: str
    points: int
    voltage_min_v: float
    voltage_max_v: float
    max_abs_voltage_v: float
    estimated_duration_s: float
    current_compliance_a: float
    safety_current_limit_a: float
    safety_voltage_limit_v: float
    checks: dict | None
    preview_points: list[PlannedPoint]
    preview_omitted: int


def build_measurement_plan(
    recipe_path: str | Path,
    safety_dir: str | Path = "configs/safety",
    preview_count: int = 5,
) -> MeasurementPlan:
    path = Path(recipe_path)
    recipe = load_recipe(path)
    safety = load_named_safety_preset(recipe.safety_preset, safety_dir)
    return build_measurement_plan_from_objects(recipe, safety, path, preview_count)


def build_measurement_plan_from_objects(
    recipe: DrainIVRecipe,
    safety: SafetyPreset,
    recipe_path: str | Path,
    preview_count: int = 5,
) -> MeasurementPlan:
    validate_recipe_against_safety(recipe, safety)
    if preview_count < 1:
        raise ValueError("preview_count must be >= 1")

    voltages = sweep_voltages(recipe.sweep)
    delays = sweep_delays(recipe.sweep)
    planned_points = [
        PlannedPoint(index=index, voltage_v=float(voltage), delay_s=float(delay))
        for index, (voltage, delay) in enumerate(zip(voltages, delays))
    ]
    preview_points, preview_omitted = preview_planned_points(planned_points, preview_count)

    return MeasurementPlan(
        recipe_path=Path(recipe_path),
        measurement_name=recipe.measurement_name,
        sample_id=recipe.experiment.sample_id,
        device_id=recipe.experiment.device_id,
        operator=recipe.experiment.operator,
        tags=recipe.experiment.tags,
        safety_preset=recipe.safety_preset,
        address=recipe.instrument.address,
        terminal=recipe.instrument.terminal,
        voltage_range_v=recipe.instrument.voltage_range_v,
        current_range_a=recipe.instrument.current_range_a,
        nplc=recipe.instrument.nplc,
        output_directory=recipe.output.directory,
        sweep_mode=recipe.sweep.mode,
        points=len(planned_points),
        voltage_min_v=min(voltages),
        voltage_max_v=max(voltages),
        max_abs_voltage_v=max(abs(voltage) for voltage in voltages),
        estimated_duration_s=sum(delays),
        current_compliance_a=recipe.sweep.current_compliance_a,
        safety_current_limit_a=safety.max_abs_current_a,
        safety_voltage_limit_v=safety.max_abs_voltage_v,
        checks=recipe.checks.model_dump(mode="json") if recipe.checks is not None else None,
        preview_points=preview_points,
        preview_omitted=preview_omitted,
    )


def preview_planned_points(points: list[PlannedPoint], preview_count: int) -> tuple[list[PlannedPoint], int]:
    if len(points) <= preview_count * 2:
        return points, 0
    return points[:preview_count] + points[-preview_count:], len(points) - preview_count * 2


def format_measurement_plan(plan: MeasurementPlan) -> str:
    def fmt_optional(value: float | None, unit: str) -> str:
        if value is None:
            return "auto"
        suffix = f" {unit}" if unit else ""
        return f"{value:.6g}{suffix}"

    lines = [
        "Measurement plan",
        f"Recipe: {plan.recipe_path}",
        f"Measurement: {plan.measurement_name}",
        f"Sample: {plan.sample_id or 'n/a'}",
        f"Device: {plan.device_id or 'n/a'}",
        f"Operator: {plan.operator or 'n/a'}",
        f"Tags: {', '.join(plan.tags) if plan.tags else 'none'}",
        f"Output directory: {plan.output_directory}",
        "",
        "Instrument",
        f"- Address: {plan.address}",
        f"- Terminal: {plan.terminal or 'unchanged'}",
        f"- Voltage range: {fmt_optional(plan.voltage_range_v, 'V')}",
        f"- Current range: {fmt_optional(plan.current_range_a, 'A')}",
        f"- NPLC: {fmt_optional(plan.nplc, '')}",
        "",
        "Safety",
        f"- Preset: {plan.safety_preset}",
        f"- Safety voltage limit: {plan.safety_voltage_limit_v:.6g} V",
        f"- Safety current limit: {plan.safety_current_limit_a:.6g} A",
        f"- Instrument current compliance: {plan.current_compliance_a:.6g} A",
        "",
        "Quality checks",
        *format_quality_checks(plan.checks),
        "",
        "Sweep",
        f"- Mode: {plan.sweep_mode}",
        f"- Points: {plan.points}",
        f"- Voltage span: {plan.voltage_min_v:.6g} V to {plan.voltage_max_v:.6g} V",
        f"- Max abs voltage: {plan.max_abs_voltage_v:.6g} V",
        f"- Estimated minimum duration: {plan.estimated_duration_s:.6g} s",
        "",
        "Point preview",
    ]
    lines.extend(format_point_preview(plan.preview_points, plan.preview_omitted))
    return "\n".join(lines)


def format_point_preview(points: list[PlannedPoint], omitted: int) -> list[str]:
    lines: list[str] = []
    last_index: int | None = None
    for point in points:
        if last_index is not None and point.index != last_index + 1 and omitted > 0:
            lines.append(f"- ... {omitted} points omitted ...")
        lines.append(f"- #{point.index + 1}: V={point.voltage_v:.6g} V, delay={point.delay_s:.6g} s")
        last_index = point.index
    return lines


def format_quality_checks(checks: dict | None) -> list[str]:
    if not checks:
        return ["- none"]
    lines = [f"- Require completed: {checks.get('require_completed', True)}"]
    if checks.get("min_points") is not None:
        lines.append(f"- Min points: {checks['min_points']}")
    resistance = checks.get("fitted_resistance_ohm")
    if resistance:
        lines.append(
            (
                "- Fitted resistance: "
                f"{resistance.get('min_ohm', 'n/a')} ohm to {resistance.get('max_ohm', 'n/a')} ohm"
            )
        )
    return lines
