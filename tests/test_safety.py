import pytest

from pytransport.errors import SafetyLimitError
from pytransport.recipes import DrainIVRecipe, SafetyPreset
from pytransport.safety import validate_point_current, validate_recipe_against_safety


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
