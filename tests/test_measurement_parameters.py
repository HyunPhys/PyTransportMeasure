from pathlib import Path

from pytransport.measurement_parameters import (
    assert_required_smu_parameters_for_hardware,
    format_measurement_parameter_issues,
    missing_explicit_nplc,
    missing_required_smu_hardware_parameters,
)
from pytransport.recipes import AcLockInRecipe, DrainIVRecipe


def test_missing_explicit_nplc_reports_keithley_roles(tmp_path: Path):
    recipe = DrainIVRecipe.model_validate(
        {
            "measurement_name": "missing_nplc",
            "instrument": {"id": "keithley_2450", "address": "GPIB0::2::INSTR"},
            "sweep": {
                "start_v": -0.001,
                "stop_v": 0.001,
                "points": 3,
                "delay_s": 0,
                "current_compliance_a": 1e-7,
            },
            "output": {"directory": tmp_path},
        }
    )

    issues = missing_explicit_nplc(recipe)

    assert len(issues) == 1
    assert issues[0].role == "instrument"
    assert issues[0].parameter == "nplc"
    text = format_measurement_parameter_issues(issues)
    assert "instrument.nplc" in text
    assert "sets Keithley current integration time" in text
    assert "Keithley 2450 hardware parameter policy" in text


def test_missing_required_smu_hardware_parameters_reports_ranges_and_nplc(tmp_path: Path):
    recipe = DrainIVRecipe.model_validate(
        {
            "measurement_name": "missing_smu_parameters",
            "instrument": {"id": "keithley_2450", "address": "GPIB0::2::INSTR"},
            "sweep": {
                "start_v": -0.001,
                "stop_v": 0.001,
                "points": 3,
                "delay_s": 0,
                "current_compliance_a": 1e-7,
            },
            "output": {"directory": tmp_path},
        }
    )

    issues = missing_required_smu_hardware_parameters(recipe)

    assert [(issue.role, issue.parameter) for issue in issues] == [
        ("instrument", "nplc"),
        ("instrument", "voltage_range_v"),
        ("instrument", "current_range_a"),
    ]
    text = format_measurement_parameter_issues(issues)
    assert "instrument.voltage_range_v" in text
    assert "instrument.current_range_a" in text


def test_required_smu_hardware_parameters_pass_when_explicit(tmp_path: Path):
    recipe = DrainIVRecipe.model_validate(
        {
            "measurement_name": "explicit_smu_parameters",
            "instrument": {
                "id": "keithley_2450",
                "address": "GPIB0::2::INSTR",
                "nplc": 1.0,
                "voltage_range_v": 0.2,
                "current_range_a": 1e-7,
            },
            "sweep": {
                "start_v": -0.001,
                "stop_v": 0.001,
                "points": 3,
                "delay_s": 0,
                "current_compliance_a": 1e-7,
            },
            "output": {"directory": tmp_path},
        }
    )

    assert_required_smu_parameters_for_hardware(recipe)


def test_missing_explicit_nplc_respects_role_filter(tmp_path: Path):
    recipe = AcLockInRecipe.model_validate(
        {
            "measurement_name": "ac",
            "source_instrument": {"id": "keithley_2450", "address": "GPIB0::2::INSTR"},
            "lockin": {"enabled": True, "address": "GPIB0::4::INSTR"},
            "bias_sweep": {
                "start_v": -0.001,
                "stop_v": 0.001,
                "points": 3,
                "delay_s": 0,
                "current_compliance_a": 1e-7,
            },
            "output": {"directory": tmp_path},
        }
    )

    assert missing_explicit_nplc(recipe, roles=("gate1", "gate2")) == ()
    assert missing_explicit_nplc(recipe, roles=("source",))[0].role == "source"
