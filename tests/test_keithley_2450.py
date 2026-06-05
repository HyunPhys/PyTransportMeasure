from pytransport.instruments.base import SMUVoltageSourceConfig
from pytransport.instruments.keithley_2450 import Keithley2450


class FakeVisaInstrument:
    def __init__(self):
        self.commands = []
        self.errors = []
        self.language = "SCPI"
        self.current_remote_sense = "0"

    def write(self, command):
        self.commands.append(command)
        if command.startswith(":SOUR:VOLT:ILIM "):
            self.errors.append('-113,"Undefined SCPI header"')
        if command == ":SENS:CURR:RSEN ON":
            self.current_remote_sense = "1"
        if command == ":SENS:CURR:RSEN OFF":
            self.current_remote_sense = "0"

    def query(self, command):
        if command == "*IDN?":
            return "KEITHLEY INSTRUMENTS,MODEL 2450,1234567,1.0"
        if command == "*LANG?":
            return self.language
        if command == ":SOUR:FUNC?":
            return "VOLT"
        if command == ":SENS:FUNC?":
            return '"CURR"'
        if command == ":ROUT:TERM?":
            return "FRON"
        if command == ":SENS:CURR:NPLC?":
            return "1.0"
        if command == ":SENS:CURR:RANG?":
            return "0.0002"
        if command == ":SENS:CURR:RANG:AUTO?":
            return "0"
        if command == ":SENS:CURR:RSEN?":
            return self.current_remote_sense
        if command == ":SOUR:VOLT:RANG?":
            return "0.2"
        if command == ":SOUR:VOLT:DEL?":
            return "0.05"
        if command == ":SOUR:VOLT:READ:BACK?":
            return "1"
        if command == ":SOUR:VOLT:ILIMIT?":
            return "0.0002"
        assert command == ":SYST:ERR?"
        if self.errors:
            return self.errors.pop(0)
        return '0,"No error"'


def test_keithley_current_limit_falls_back_after_undefined_header():
    smu = Keithley2450("FAKE")
    smu._inst = FakeVisaInstrument()

    smu.configure_voltage_source(
        SMUVoltageSourceConfig(
            current_compliance_a=2e-4,
            voltage_range_v=0.2,
            current_range_a=2e-4,
            terminal="FRONT",
            nplc=1.0,
            source_delay_s=0.05,
        )
    )

    assert smu.current_limit_command == ":SOUR:VOLT:ILIMIT {value}"
    assert ":ROUT:TERM FRONT" in smu.inst.commands
    assert ":SENS:CURR:NPLC 1.0" in smu.inst.commands
    assert ":SOUR:VOLT:RANG 0.2" in smu.inst.commands
    assert ":SOUR:VOLT:DEL 0.05" in smu.inst.commands
    assert ":SENS:CURR:RANG 0.0002" in smu.inst.commands
    assert ":SOUR:VOLT:ILIMIT 0.0002" in smu.inst.commands
    assert not any(command.startswith(":FORM:ELEM") for command in smu.inst.commands)
    assert not any(command.startswith(":SENS:CURR:RSEN") for command in smu.inst.commands)


def test_keithley_rejects_non_scpi_command_set():
    smu = Keithley2450("FAKE")
    fake = FakeVisaInstrument()
    fake.language = "TSP"
    smu._inst = fake

    try:
        smu.configure_voltage_source(SMUVoltageSourceConfig(current_compliance_a=2e-4))
    except RuntimeError as exc:
        assert "must be SCPI" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError")


def test_keithley_probe_reads_identity_language_and_error():
    smu = Keithley2450("GPIB0::2::INSTR")
    smu._inst = FakeVisaInstrument()

    result = smu.probe()

    assert result["address"] == "GPIB0::2::INSTR"
    assert result["idn"].startswith("KEITHLEY INSTRUMENTS,MODEL 2450")
    assert result["language"] == "SCPI"
    assert result["system_error"] == '0,"No error"'


def test_keithley_voltage_source_config_readback_uses_accepted_current_limit_query():
    smu = Keithley2450("FAKE")
    smu._inst = FakeVisaInstrument()
    smu.configure_voltage_source(
        SMUVoltageSourceConfig(
            current_compliance_a=2e-4,
            voltage_range_v=0.2,
            current_range_a=2e-4,
            terminal="FRONT",
            nplc=1.0,
            source_delay_s=0.05,
        )
    )

    readback = smu.read_voltage_source_config()

    assert readback["source_function"] == "VOLT"
    assert readback["sense_function"] == '"CURR"'
    assert readback["terminal"] == "FRON"
    assert readback["current_nplc"] == "1.0"
    assert readback["current_range"] == "0.0002"
    assert readback["current_range_auto"] == "0"
    assert readback["voltage_range"] == "0.2"
    assert readback["source_delay"] == "0.05"
    assert readback["voltage_readback"] == "1"
    assert readback["source_current_limit"] == "0.0002"
    assert readback["source_current_limit_query"] == ":SOUR:VOLT:ILIMIT?"


def test_keithley_current_remote_sense_uses_current_rsen_scpi():
    smu = Keithley2450("FAKE")
    smu._inst = FakeVisaInstrument()

    smu.configure_current_remote_sense(True)
    assert smu.read_current_remote_sense() == "1"
    smu.configure_current_remote_sense(False)
    assert smu.read_current_remote_sense() == "0"

    assert ":SENS:CURR:RSEN ON" in smu.inst.commands
    assert ":SENS:CURR:RSEN OFF" in smu.inst.commands


def test_keithley_current_remote_sense_requires_scpi_command_set():
    smu = Keithley2450("FAKE")
    fake = FakeVisaInstrument()
    fake.language = "TSP"
    smu._inst = fake

    try:
        smu.configure_current_remote_sense(True)
    except RuntimeError as exc:
        assert "must be SCPI" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError")
    assert ":SENS:CURR:RSEN ON" not in smu.inst.commands
