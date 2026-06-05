"""Safety checks for v0 Drain I-V measurements."""

from __future__ import annotations

from .errors import SafetyLimitError
from .recipes import (
    AcLockInRecipe,
    DrainIVRecipe,
    DualGateLockInRecipe,
    DualGateRecipe,
    PulseRecipe,
    SafetyPreset,
    SingleGateRecipe,
    gate_voltages_from_config,
    sweep_voltages,
)


def validate_active_geometry(label: str, geometry_method: str, terminal_count: int) -> None:
    if geometry_method != "two_terminal":
        raise SafetyLimitError(
            f"{label} currently supports only two_terminal geometry; requested {geometry_method}",
            triggered_limit="measurement_geometry_method",
        )
    if terminal_count != 2:
        raise SafetyLimitError(
            f"{label} currently supports only 2-terminal geometry; requested {terminal_count}-terminal",
            triggered_limit="measurement_geometry_terminal_count",
        )


def validate_lockin_voltage_geometry(
    label: str,
    geometry_method: str,
    terminal_count: int,
    lockin_input_mode: str | None,
    lockin_voltage_input: str | None,
    topology: object | None = None,
) -> None:
    if geometry_method == "two_terminal" and terminal_count == 2:
        return
    if geometry_method == "two_terminal":
        raise SafetyLimitError(
            f"{label} two_terminal geometry requires terminal_count=2; requested {terminal_count}-terminal",
            triggered_limit="measurement_geometry_terminal_count",
        )
    if geometry_method != "four_terminal":
        raise SafetyLimitError(
            f"{label} supports only two_terminal or guarded four_terminal lock-in geometry; requested {geometry_method}",
            triggered_limit="measurement_geometry_method",
        )
    if terminal_count != 4:
        raise SafetyLimitError(
            f"{label} four_terminal geometry requires terminal_count=4; requested {terminal_count}-terminal",
            triggered_limit="measurement_geometry_terminal_count",
        )
    if lockin_input_mode != "voltage":
        raise SafetyLimitError(
            f"{label} four_terminal geometry requires SR860 voltage input mode",
            triggered_limit="lockin_input_mode",
        )
    if lockin_voltage_input != "a-b":
        raise SafetyLimitError(
            f"{label} four_terminal geometry requires differential SR860 voltage input a-b",
            triggered_limit="lockin_voltage_input",
        )
    if topology is not None:
        _validate_lockin_four_terminal_topology(label, topology)


def _validate_lockin_four_terminal_topology(label: str, topology: object) -> None:
    topology_input_mode = getattr(topology, "lockin_input_mode", None)
    if topology_input_mode != "voltage":
        raise SafetyLimitError(
            f"{label} four_terminal topology requires lockin_input_mode=voltage",
            triggered_limit="topology_lockin_input_mode",
        )
    lockin_contacts = tuple(getattr(topology, "lockin_input_contacts", ()) or ())
    excitation_contacts = tuple(getattr(topology, "excitation_contacts", ()) or ())
    if len(lockin_contacts) != 2 or len(set(lockin_contacts)) != 2:
        raise SafetyLimitError(
            f"{label} four_terminal topology requires two distinct lock-in voltage contacts",
            triggered_limit="topology_lockin_input_contacts",
        )
    if len(excitation_contacts) != 2 or len(set(excitation_contacts)) != 2:
        raise SafetyLimitError(
            f"{label} four_terminal topology requires two distinct excitation contacts",
            triggered_limit="topology_excitation_contacts",
        )
    if set(lockin_contacts) & set(excitation_contacts):
        raise SafetyLimitError(
            f"{label} four_terminal topology requires voltage contacts separate from excitation contacts",
            triggered_limit="topology_contact_overlap",
        )


def validate_recipe_against_safety(recipe: DrainIVRecipe, safety: SafetyPreset) -> None:
    validate_active_geometry("Drain I-V", recipe.measurement_geometry.method, recipe.measurement_geometry.terminal_count)
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
    validate_active_geometry("Single-gate", recipe.measurement_geometry.method, recipe.measurement_geometry.terminal_count)
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


def validate_dual_gate_recipe_against_safety(recipe: DualGateRecipe, safety: SafetyPreset) -> None:
    validate_active_geometry("Dual-gate", recipe.measurement_geometry.method, recipe.measurement_geometry.terminal_count)
    drain_max_voltage = max(abs(voltage) for voltage in sweep_voltages(recipe.drain_sweep))
    gate1_max_voltage = max(abs(voltage) for voltage in gate_voltages_from_config(recipe.gate1_sweep))
    gate2_max_voltage = max(abs(voltage) for voltage in gate_voltages_from_config(recipe.gate2_sweep))
    max_recipe_voltage = max(drain_max_voltage, gate1_max_voltage, gate2_max_voltage)
    if max_recipe_voltage > safety.max_abs_voltage_v:
        raise SafetyLimitError(
            (
                f"Recipe voltage range reaches {max_recipe_voltage:g} V, "
                f"above safety limit {safety.max_abs_voltage_v:g} V"
            ),
            triggered_limit="max_abs_voltage_v",
        )
    for label, compliance in [
        ("Drain", recipe.drain_sweep.current_compliance_a),
        ("Gate1", recipe.gate1_sweep.current_compliance_a),
        ("Gate2", recipe.gate2_sweep.current_compliance_a),
    ]:
        if compliance > safety.max_abs_current_a:
            raise SafetyLimitError(
                (
                    f"{label} compliance {compliance:g} A, "
                    f"above safety limit {safety.max_abs_current_a:g} A"
                ),
                triggered_limit=f"{label.lower()}_max_abs_current_a",
            )


def validate_ac_lockin_recipe_against_safety(recipe: AcLockInRecipe, safety: SafetyPreset) -> None:
    validate_lockin_voltage_geometry(
        "AC lock-in",
        recipe.measurement_geometry.method,
        recipe.measurement_geometry.terminal_count,
        recipe.lockin.input_mode,
        recipe.lockin.voltage_input,
        topology=recipe.topology,
    )
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


def validate_dual_gate_lockin_recipe_against_safety(recipe: DualGateLockInRecipe, safety: SafetyPreset) -> None:
    validate_lockin_voltage_geometry(
        "Dual-gate lock-in",
        recipe.measurement_geometry.method,
        recipe.measurement_geometry.terminal_count,
        recipe.lockin.input_mode,
        recipe.lockin.voltage_input,
        topology=recipe.topology,
    )
    gate1_max_voltage = max(abs(voltage) for voltage in gate_voltages_from_config(recipe.gate1_sweep))
    gate2_max_voltage = max(abs(voltage) for voltage in gate_voltages_from_config(recipe.gate2_sweep))
    max_recipe_voltage = max(gate1_max_voltage, gate2_max_voltage)
    if max_recipe_voltage > safety.max_abs_voltage_v:
        raise SafetyLimitError(
            (
                f"Gate voltage range reaches {max_recipe_voltage:g} V, "
                f"above safety limit {safety.max_abs_voltage_v:g} V"
            ),
            triggered_limit="max_abs_voltage_v",
        )
    for label, compliance in [
        ("Gate1", recipe.gate1_sweep.current_compliance_a),
        ("Gate2", recipe.gate2_sweep.current_compliance_a),
    ]:
        if compliance > safety.max_abs_current_a:
            raise SafetyLimitError(
                (
                    f"{label} compliance {compliance:g} A, "
                    f"above safety limit {safety.max_abs_current_a:g} A"
                ),
                triggered_limit=f"{label.lower()}_max_abs_current_a",
            )


def validate_pulse_recipe_against_safety(recipe: PulseRecipe, safety: SafetyPreset) -> None:
    validate_active_geometry("Pulse", recipe.measurement_geometry.method, recipe.measurement_geometry.terminal_count)
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
