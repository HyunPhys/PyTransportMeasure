import math

import pytest
from pydantic import ValidationError

from pytransport.instruments.base import LockInReading
from pytransport.instruments.fake import FakeLockIn
from pytransport.instruments.srs_sr860 import SRS_SR860
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


class FakeSR860VisaInstrument:
    def __init__(self):
        self.queries = []
        self.closed = False

    def query(self, command):
        self.queries.append(command)
        if command == "*IDN?":
            return "Stanford_Research_Systems,SR860,000111,v1.23"
        if command == "ERRS?":
            return "0"
        if command == "LIAS?":
            return "0"
        if command == "RSRC?":
            return "0"
        if command == "FREQ?":
            return "17.777"
        if command == "SLVL?":
            return "0.01"
        if command == "IVMD?":
            return "0"
        if command == "ISRC?":
            return "0"
        if command == "ICPL?":
            return "0"
        if command == "IGND?":
            return "0"
        if command == "IRNG?":
            return "4"
        if command == "SCAL?":
            return "18"
        if command == "OFLT?":
            return "10"
        if command == "OFSL?":
            return "3"
        if command == "SYNC?":
            return "0"
        if command == "SNAP? X,Y,R":
            return "1.0e-6,2.0e-6,2.2360679e-6"
        if command == "OUTP? THeta":
            return "63.4349488"
        raise AssertionError(f"Unexpected query: {command}")

    def close(self):
        self.closed = True


def test_srs_sr860_probe_reads_identity_and_status():
    lockin = SRS_SR860("GPIB0::4::INSTR")
    fake = FakeSR860VisaInstrument()
    lockin._inst = fake

    result = lockin.probe()

    assert result["address"] == "GPIB0::4::INSTR"
    assert result["idn"].startswith("Stanford_Research_Systems,SR860")
    assert result["error_status"] == "0"
    assert result["lia_status"] == "0"
    assert result["setting_reference_frequency_hz"] == "17.777"
    assert result["setting_filter_slope_index"] == "3"
    assert fake.queries == [
        "*IDN?",
        "ERRS?",
        "LIAS?",
        "RSRC?",
        "FREQ?",
        "SLVL?",
        "IVMD?",
        "ISRC?",
        "ICPL?",
        "IGND?",
        "IRNG?",
        "SCAL?",
        "OFLT?",
        "OFSL?",
        "SYNC?",
    ]


def test_srs_sr860_read_channels_uses_snap_for_xyr_and_outp_for_theta():
    lockin = SRS_SR860("GPIB0::4::INSTR")
    fake = FakeSR860VisaInstrument()
    lockin._inst = fake

    reading = lockin.read_channels()

    assert reading.x_v == pytest.approx(1e-6)
    assert reading.y_v == pytest.approx(2e-6)
    assert reading.r_v == pytest.approx(2.2360679e-6)
    assert reading.theta_deg == pytest.approx(63.4349488)
    assert fake.queries == ["SNAP? X,Y,R", "OUTP? THeta"]


def test_srs_sr860_rejects_bad_snap_response_shape():
    lockin = SRS_SR860("GPIB0::4::INSTR")

    class BadSnapInstrument(FakeSR860VisaInstrument):
        def query(self, command):
            if command == "SNAP? X,Y,R":
                return "1,2"
            return super().query(command)

    lockin._inst = BadSnapInstrument()

    with pytest.raises(RuntimeError, match="SNAP"):
        lockin.read_channels()
