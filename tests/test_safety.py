import pytest

from pytransport.errors import SafetyLimitError
from pytransport.recipes import DrainIVRecipe, SafetyPreset
from pytransport.safety import validate_active_geometry, validate_point_current, validate_recipe_against_safety


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
