from pathlib import Path

from pytransport.measurement_parameters import (
    audit_smu_hardware_parameters,
    assert_required_smu_parameters_for_hardware,
    format_measurement_parameter_issues,
    format_smu_hardware_parameter_audit,
    missing_explicit_nplc,
    missing_required_smu_hardware_parameters,
    smu_hardware_parameter_audit_to_dict,
)
from pytransport.recipes import AcLockInRecipe, DrainIVRecipe, DualGateLockInRecipe


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


def test_smu_hardware_parameter_audit_reports_dual_gate_lockin_roles(tmp_path: Path):
    recipe = DualGateLockInRecipe.model_validate(
        {
            "measurement_name": "audit_dual_gate_lockin",
            "gate1_instrument": {
                "id": "keithley_2450",
                "address": "GPIB0::2::INSTR",
                "terminal": "FRONT",
                "voltage_range_v": 0.2,
                "current_range_a": 1e-9,
                "nplc": 1.0,
                "source_delay_s": 0.05,
            },
            "gate2_instrument": {
                "id": "keithley_2450",
                "address": "GPIB0::3::INSTR",
                "terminal": "REAR",
                "voltage_range_v": 0.3,
                "current_range_a": 2e-9,
            },
            "lockin": {"enabled": True, "address": "GPIB0::4::INSTR"},
            "topology": {
                "source_contact": "S",
                "drain_contact": "D",
                "lockin_input_contacts": ["V1", "V2"],
                "excitation_contacts": ["S", "D"],
                "excitation_amplitude_v": 0.01,
            },
            "gate1_sweep": {
                "start_v": -0.1,
                "stop_v": 0.1,
                "points": 3,
                "settle_s": 0,
                "current_compliance_a": 1e-9,
            },
            "gate2_sweep": {
                "start_v": -0.1,
                "stop_v": 0.1,
                "points": 3,
                "settle_s": 0,
                "current_compliance_a": 2e-9,
            },
            "output": {"directory": tmp_path},
        }
    )

    audits = audit_smu_hardware_parameters(recipe)
    payload = smu_hardware_parameter_audit_to_dict(audits)
    text = format_smu_hardware_parameter_audit(audits)

    assert [audit.role for audit in audits] == ["gate1", "gate2"]
    assert audits[0].current_compliance_a == 1e-9
    assert audits[0].ok_for_hardware is True
    assert audits[1].missing_required_parameters == ("nplc",)
    assert payload["ok_for_hardware"] is False
    assert payload["roles"][1]["missing_required_parameters"] == ["nplc"]
    assert "| gate1 | keithley_2450 | `GPIB0::2::INSTR` | FRONT | 0.2 | 1e-09 | 1 | 0.05 | 1e-09 | PASS |" in text
    assert "MISSING nplc" in text
