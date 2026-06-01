"""Safety checks for v0 Drain I-V measurements."""

from __future__ import annotations

from .errors import SafetyLimitError
from .recipes import AcLockInRecipe, DrainIVRecipe, PulseRecipe, SafetyPreset, SingleGateRecipe, gate_voltages_from_config, sweep_voltages


def validate_recipe_against_safety(recipe: DrainIVRecipe, safety: SafetyPreset) -> None:
    max_recipe_voltage = max(abs(voltage) for voltage in sweep_voltages(recipe.sweep))
    if max_recipe_voltage > safety.max_abs_voltage_v:
        raise SafetyLimitError(
            (
                f"Recipe voltage range reaches {max_recipe_voltage:g} V, "
                f"above safety limit {safety.max_abs_voltage_v:g} V"
            ),
            triggered_limit="max_abs_voltage_v",
        )
    if recipe.sweep.current_compliance_a > safety.max_abs_current_a:
        raise SafetyLimitError(
            (
                f"Recipe compliance {recipe.sweep.current_compliance_a:g} A, "
                f"above safety limit {safety.max_abs_current_a:g} A"
            ),
            triggered_limit="max_abs_current_a",
        )


def validate_single_gate_recipe_against_safety(recipe: SingleGateRecipe, safety: SafetyPreset) -> None:
    drain_max_voltage = max(abs(voltage) for voltage in sweep_voltages(recipe.drain_sweep))
    gate_max_voltage = max(abs(voltage) for voltage in gate_voltages_from_config(recipe.gate_sweep))
    max_recipe_voltage = max(drain_max_voltage, gate_max_voltage)
    if max_recipe_voltage > safety.max_abs_voltage_v:
        raise SafetyLimitError(
            (
                f"Recipe voltage range reaches {max_recipe_voltage:g} V, "
                f"above safety limit {safety.max_abs_voltage_v:g} V"
            ),
            triggered_limit="max_abs_voltage_v",
        )
    if recipe.drain_sweep.current_compliance_a > safety.max_abs_current_a:
        raise SafetyLimitError(
            (
                f"Drain compliance {recipe.drain_sweep.current_compliance_a:g} A, "
                f"above safety limit {safety.max_abs_current_a:g} A"
            ),
            triggered_limit="drain_max_abs_current_a",
        )
    if recipe.gate_sweep.current_compliance_a > safety.max_abs_current_a:
        raise SafetyLimitError(
            (
                f"Gate compliance {recipe.gate_sweep.current_compliance_a:g} A, "
                f"above safety limit {safety.max_abs_current_a:g} A"
            ),
            triggered_limit="gate_max_abs_current_a",
        )


def validate_ac_lockin_recipe_against_safety(recipe: AcLockInRecipe, safety: SafetyPreset) -> None:
    max_recipe_voltage = max(abs(voltage) for voltage in sweep_voltages(recipe.bias_sweep))
    if max_recipe_voltage > safety.max_abs_voltage_v:
        raise SafetyLimitError(
            (
                f"Bias sweep reaches {max_recipe_voltage:g} V, "
                f"above safety limit {safety.max_abs_voltage_v:g} V"
            ),
            triggered_limit="max_abs_voltage_v",
        )
    if recipe.bias_sweep.current_compliance_a > safety.max_abs_current_a:
        raise SafetyLimitError(
            (
                f"Source compliance {recipe.bias_sweep.current_compliance_a:g} A, "
                f"above safety limit {safety.max_abs_current_a:g} A"
            ),
            triggered_limit="source_max_abs_current_a",
        )


def validate_pulse_recipe_against_safety(recipe: PulseRecipe, safety: SafetyPreset) -> None:
    max_recipe_voltage = max(abs(recipe.pulse.base_v), abs(recipe.pulse.amplitude_v))
    if max_recipe_voltage > safety.max_abs_voltage_v:
        raise SafetyLimitError(
            (
                f"Pulse voltage reaches {max_recipe_voltage:g} V, "
                f"above safety limit {safety.max_abs_voltage_v:g} V"
            ),
            triggered_limit="max_abs_voltage_v",
        )
    if recipe.pulse.current_compliance_a > safety.max_abs_current_a:
        raise SafetyLimitError(
            (
                f"Pulse compliance {recipe.pulse.current_compliance_a:g} A, "
                f"above safety limit {safety.max_abs_current_a:g} A"
            ),
            triggered_limit="pulse_max_abs_current_a",
        )


def validate_point_current(current_a: float, safety: SafetyPreset) -> None:
    if abs(current_a) > safety.max_abs_current_a:
        raise SafetyLimitError(
            (
                f"Measured current {current_a:g} A exceeded software limit "
                f"{safety.max_abs_current_a:g} A"
            ),
            triggered_limit="measured_current_a",
        )
