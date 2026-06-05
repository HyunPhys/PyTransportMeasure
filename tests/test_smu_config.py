import pytest

from pytransport.smu_config import build_voltage_source_config, voltage_source_config_snapshot


def test_build_voltage_source_config_from_instrument_dict():
    config = build_voltage_source_config(
        {
            "voltage_range_v": "0.2",
            "current_range_a": "1e-6",
            "terminal": "FRONT",
            "nplc": "1.0",
        },
        current_compliance_a="1e-7",
    )

    assert config.current_compliance_a == pytest.approx(1e-7)
    assert config.voltage_range_v == pytest.approx(0.2)
    assert config.current_range_a == pytest.approx(1e-6)
    assert config.terminal == "FRONT"
    assert config.nplc == pytest.approx(1.0)
    assert voltage_source_config_snapshot(config) == {
        "current_compliance_a": 1e-7,
        "voltage_range_v": 0.2,
        "current_range_a": 1e-6,
        "terminal": "FRONT",
        "nplc": 1.0,
    }
