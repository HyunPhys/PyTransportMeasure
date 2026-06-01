import math

import pytest
from pydantic import ValidationError

from pytransport.instruments.base import LockInReading
from pytransport.instruments.fake import FakeLockIn
from pytransport.recipes import LockInConfig


def test_lockin_reading_uses_standard_column_names():
    reading = LockInReading(x_v=1.0, y_v=2.0, r_v=3.0, theta_deg=4.0)

    assert reading.to_dict() == {
        "lockin_x_v": 1.0,
        "lockin_y_v": 2.0,
        "lockin_r_v": 3.0,
        "lockin_theta_deg": 4.0,
    }


def test_fake_lockin_reads_deterministic_channels_without_noise():
    lockin = FakeLockIn(signal_r_v=2.0, phase_deg=60.0, noise_std_v=0.0)
    lockin.connect()

    reading = lockin.read_channels()

    assert lockin.probe()["idn"] == "FAKE,LOCKIN,SR860-DRY-RUN,0"
    assert reading.x_v == pytest.approx(1.0)
    assert reading.y_v == pytest.approx(math.sqrt(3.0))
    assert reading.r_v == pytest.approx(2.0)
    assert reading.theta_deg == pytest.approx(60.0)
    lockin.close()
    assert lockin.connected is False


def test_lockin_config_requires_address_only_when_enabled():
    disabled = LockInConfig.model_validate({"enabled": False})
    assert disabled.address is None
    assert disabled.channels == ["x", "y", "r", "theta"]

    enabled = LockInConfig.model_validate({"enabled": True, "address": "GPIB0::4::INSTR"})
    assert enabled.id == "srs_sr860"
    assert enabled.read_timing == "after_dc_settle"

    with pytest.raises(ValidationError):
        LockInConfig.model_validate({"enabled": True})
