import pytest

from pytransport.smu_config import (
    build_voltage_source_config,
    compare_voltage_source_config_readback,
    raise_for_voltage_source_config_readback_mismatch,
    read_voltage_source_config_if_available,
    voltage_source_config_snapshot,
)


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


def test_read_voltage_source_config_if_available_reports_missing_and_errors():
    assert read_voltage_source_config_if_available(object()) is None

    class BrokenReader:
        def read_voltage_source_config(self):
            raise RuntimeError("boom")

    assert read_voltage_source_config_if_available(BrokenReader()) == {"readback_error": "RuntimeError: boom"}


def test_compare_voltage_source_config_readback_detects_mismatch():
    config = build_voltage_source_config({"nplc": 1.0, "current_range_a": 1e-6}, current_compliance_a=1e-7)
    check = compare_voltage_source_config_readback(
        config,
        {
            "source_function": "VOLT",
            "sense_function": '"CURR"',
            "voltage_readback": "1",
            "source_current_limit": "1e-7",
            "current_nplc": "0.01",
            "current_range": "1e-6",
            "current_range_auto": "0",
        },
    )

    assert check["matched"] is False
    failed = [item["field"] for item in check["checks"] if not item["matched"]]
    assert failed == ["current_nplc"]

    with pytest.raises(Exception, match="readback mismatch"):
        raise_for_voltage_source_config_readback_mismatch("source", check)
