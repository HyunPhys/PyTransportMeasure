"""Recipe validation reports for pre-hardware checks."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .recipes import DrainIVRecipe, SafetyPreset, load_named_safety_preset, load_recipe, sweep_delays, sweep_voltages
from .safety import validate_recipe_against_safety


@dataclass(frozen=True)
class RecipeValidationReport:
    recipe_path: Path
    measurement_name: str
    sample_id: str | None
    device_id: str | None
    cooldown_id: str | None
    contact_geometry: str | None
    lab_notebook_ref: str | None
    operator: str | None
    tags: list[str]
    safety_preset: str
    address: str
    terminal: str | None
    voltage_range_v: float | None
    current_range_a: float | None
    sweep_mode: str
    voltage_min_v: float
    voltage_max_v: float
    points: int
    current_compliance_a: float
    estimated_duration_s: float
    max_abs_sweep_voltage_v: float
    max_abs_safety_voltage_v: float
    max_abs_safety_current_a: float


def validate_recipe_file(
    recipe_path: str | Path,
    safety_dir: str | Path = "configs/safety",
) -> RecipeValidationReport:
    path = Path(recipe_path)
    recipe = load_recipe(path)
    safety = load_named_safety_preset(recipe.safety_preset, safety_dir)
    return validate_recipe(recipe, safety, path)


def validate_recipe(
    recipe: DrainIVRecipe,
    safety: SafetyPreset,
    recipe_path: str | Path,
) -> RecipeValidationReport:
    validate_recipe_against_safety(recipe, safety)
    voltages = sweep_voltages(recipe.sweep)
    delays = sweep_delays(recipe.sweep)
    max_abs_sweep_voltage = max(abs(voltage) for voltage in voltages)
    return RecipeValidationReport(
        recipe_path=Path(recipe_path),
        measurement_name=recipe.measurement_name,
        sample_id=recipe.experiment.sample_id,
        device_id=recipe.experiment.device_id,
        cooldown_id=recipe.experiment.cooldown_id,
        contact_geometry=recipe.experiment.contact_geometry,
        lab_notebook_ref=recipe.experiment.lab_notebook_ref,
        operator=recipe.experiment.operator,
        tags=recipe.experiment.tags,
        safety_preset=recipe.safety_preset,
        address=recipe.instrument.address,
        terminal=recipe.instrument.terminal,
        voltage_range_v=recipe.instrument.voltage_range_v,
        current_range_a=recipe.instrument.current_range_a,
        sweep_mode=recipe.sweep.mode,
        voltage_min_v=min(voltages),
        voltage_max_v=max(voltages),
        points=len(voltages),
        current_compliance_a=recipe.sweep.current_compliance_a,
        estimated_duration_s=sum(delays),
        max_abs_sweep_voltage_v=max_abs_sweep_voltage,
        max_abs_safety_voltage_v=safety.max_abs_voltage_v,
        max_abs_safety_current_a=safety.max_abs_current_a,
    )


def format_validation_report(report: RecipeValidationReport) -> str:
    def fmt(value: float | None, unit: str = "") -> str:
        if value is None:
            return "auto"
        return f"{value:.6g}{unit}"

    return "\n".join(
        [
            "Recipe validation: OK",
            f"Recipe: {report.recipe_path}",
            f"Measurement: {report.measurement_name}",
            f"Sample: {report.sample_id or 'n/a'}",
            f"Device: {report.device_id or 'n/a'}",
            f"Cooldown: {report.cooldown_id or 'n/a'}",
            f"Contact geometry: {report.contact_geometry or 'n/a'}",
            f"Lab notebook: {report.lab_notebook_ref or 'n/a'}",
            f"Operator: {report.operator or 'n/a'}",
            f"Tags: {', '.join(report.tags) if report.tags else 'none'}",
            f"Safety preset: {report.safety_preset}",
            f"Instrument address: {report.address}",
            f"Terminal: {report.terminal or 'unchanged'}",
            f"Voltage range: {fmt(report.voltage_range_v, ' V')}",
            f"Current range: {fmt(report.current_range_a, ' A')}",
            f"Sweep mode: {report.sweep_mode}",
            f"Sweep voltage span: {report.voltage_min_v:.6g} V to {report.voltage_max_v:.6g} V",
            f"Sweep points: {report.points}",
            f"Estimated minimum duration: {report.estimated_duration_s:.6g} s",
            f"Current compliance: {report.current_compliance_a:.6g} A",
            f"Safety voltage limit: {report.max_abs_safety_voltage_v:.6g} V",
            f"Safety current limit: {report.max_abs_safety_current_a:.6g} A",
        ]
    )
