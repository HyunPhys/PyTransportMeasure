from pathlib import Path

from pytransport.measurement_parameters import (
    format_measurement_parameter_issues,
    missing_explicit_nplc,
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
    assert "instrument.nplc" in format_measurement_parameter_issues(issues)


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
