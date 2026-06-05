import pytest

from pytransport.errors import SafetyLimitError
from pytransport.recipes import AcLockInRecipe, DrainIVRecipe, DualGateLockInRecipe, SafetyPreset
from pytransport.safety import (
    validate_ac_lockin_recipe_against_safety,
    validate_active_geometry,
    validate_dual_gate_lockin_recipe_against_safety,
    validate_point_current,
    validate_recipe_against_safety,
)


def make_recipe(**sweep_overrides):
    sweep = {
        "start_v": -0.1,
        "stop_v": 0.1,
        "points": 3,
        "delay_s": 0,
        "current_compliance_a": 1e-7,
    }
    sweep.update(sweep_overrides)
    return DrainIVRecipe.model_validate(
        {
            "measurement_name": "test",
            "instrument": {"address": "FAKE"},
            "sweep": sweep,
        }
    )


def make_safety():
    return SafetyPreset(
        name="nano_device_safe",
        max_abs_voltage_v=1.0,
        max_abs_current_a=1e-6,
        default_current_compliance_a=1e-7,
    )


def test_recipe_voltage_limit_rejected():
    with pytest.raises(SafetyLimitError) as error:
        validate_recipe_against_safety(make_recipe(stop_v=2.0), make_safety())
    assert error.value.triggered_limit == "max_abs_voltage_v"


def test_point_current_limit_rejected():
    with pytest.raises(SafetyLimitError) as error:
        validate_point_current(2e-6, make_safety())
    assert error.value.triggered_limit == "measured_current_a"


def test_four_terminal_geometry_is_blocked_until_runner_support_exists():
    recipe = DrainIVRecipe.model_validate(
        {
            "measurement_name": "future_four_terminal",
            "measurement_geometry": {"method": "four_terminal", "terminal_count": 4},
            "instrument": {"address": "FAKE"},
            "sweep": {
                "start_v": -0.01,
                "stop_v": 0.01,
                "points": 3,
                "delay_s": 0,
                "current_compliance_a": 1e-7,
            },
        }
    )

    with pytest.raises(SafetyLimitError) as error:
        validate_recipe_against_safety(recipe, make_safety())
    assert error.value.triggered_limit == "measurement_geometry_method"


def test_active_geometry_guard_checks_method_before_terminal_count():
    with pytest.raises(SafetyLimitError) as error:
        validate_active_geometry("Drain I-V", "four_terminal", 4)
    assert error.value.triggered_limit == "measurement_geometry_method"
    assert "four_terminal" in str(error.value)


def test_active_geometry_guard_checks_terminal_count_for_two_terminal_method():
    with pytest.raises(SafetyLimitError) as error:
        validate_active_geometry("Drain I-V", "two_terminal", 4)
    assert error.value.triggered_limit == "measurement_geometry_terminal_count"


def ac_lockin_four_terminal_data():
    return {
        "measurement_name": "four_terminal_ac",
        "measurement_geometry": {"method": "four_terminal", "terminal_count": 4},
        "source_instrument": {
            "id": "keithley_2450",
            "address": "GPIB0::2::INSTR",
            "voltage_range_v": 0.1,
            "current_range_a": 1e-7,
            "nplc": 1.0,
        },
        "lockin": {
            "enabled": True,
            "address": "GPIB0::4::INSTR",
            "channels": ["x", "y", "r", "theta"],
            "input_mode": "voltage",
            "voltage_input": "a-b",
        },
        "bias_sweep": {
            "mode": "linear_one_way",
            "start_v": -0.01,
            "stop_v": 0.01,
            "points": 3,
            "delay_s": 0,
            "current_compliance_a": 1e-7,
        },
    }


def dual_gate_lockin_four_terminal_data():
    return {
        "measurement_name": "four_terminal_dual_gate_lockin",
        "measurement_geometry": {"method": "four_terminal", "terminal_count": 4},
        "gate1_instrument": {
            "id": "keithley_2450",
            "address": "GPIB0::2::INSTR",
            "voltage_range_v": 0.2,
            "current_range_a": 1e-9,
            "nplc": 1.0,
        },
        "gate2_instrument": {
            "id": "keithley_2450",
            "address": "GPIB0::3::INSTR",
            "voltage_range_v": 0.2,
            "current_range_a": 1e-9,
            "nplc": 1.0,
        },
        "lockin": {
            "enabled": True,
            "address": "GPIB0::4::INSTR",
            "channels": ["x", "y", "r", "theta"],
            "input_mode": "voltage",
            "voltage_input": "a-b",
        },
        "topology": {
            "device_layout": "hall_bar",
            "gate1_role": "top_gate",
            "gate2_role": "back_gate",
            "source_contact": "S",
            "drain_contact": "D",
            "lockin_input_mode": "voltage",
            "lockin_input_contacts": ["Vxx+", "Vxx-"],
            "excitation_source": "sr860_sine_out",
            "excitation_contacts": ["S", "D"],
            "excitation_amplitude_v": 0.01,
            "current_bias_resistor_ohm": 1_000_000,
        },
        "gate1_sweep": {
            "start_v": -0.1,
            "stop_v": 0.1,
            "points": 2,
            "settle_s": 0,
            "current_compliance_a": 1e-8,
        },
        "gate2_sweep": {
            "start_v": -0.1,
            "stop_v": 0.1,
            "points": 2,
            "settle_s": 0,
            "current_compliance_a": 1e-8,
        },
    }


def test_ac_lockin_four_terminal_geometry_is_allowed_for_differential_voltage_input():
    recipe = AcLockInRecipe.model_validate(ac_lockin_four_terminal_data())

    validate_ac_lockin_recipe_against_safety(recipe, make_safety())


def test_ac_lockin_four_terminal_geometry_requires_differential_input():
    data = ac_lockin_four_terminal_data()
    data["lockin"]["voltage_input"] = "a"
    recipe = AcLockInRecipe.model_validate(data)

    with pytest.raises(SafetyLimitError) as error:
        validate_ac_lockin_recipe_against_safety(recipe, make_safety())
    assert error.value.triggered_limit == "lockin_voltage_input"


def test_dual_gate_lockin_four_terminal_geometry_is_allowed_for_separate_voltage_contacts():
    recipe = DualGateLockInRecipe.model_validate(dual_gate_lockin_four_terminal_data())

    validate_dual_gate_lockin_recipe_against_safety(recipe, make_safety())


def test_dual_gate_lockin_four_terminal_geometry_rejects_overlapping_excitation_contacts():
    data = dual_gate_lockin_four_terminal_data()
    data["topology"]["lockin_input_contacts"] = ["S", "Vxx-"]
    recipe = DualGateLockInRecipe.model_validate(data)

    with pytest.raises(SafetyLimitError) as error:
        validate_dual_gate_lockin_recipe_against_safety(recipe, make_safety())
    assert error.value.triggered_limit == "topology_contact_overlap"
