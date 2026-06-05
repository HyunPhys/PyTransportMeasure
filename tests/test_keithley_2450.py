from pytransport.instruments.base import SMUVoltageSourceConfig
from pytransport.instruments.keithley_2450 import Keithley2450


class FakeVisaInstrument:
    def __init__(self):
        self.commands = []
        self.errors = []
        self.language = "SCPI"

    def write(self, command):
        self.commands.append(command)
        if command.startswith(":SOUR:VOLT:ILIM "):
            self.errors.append('-113,"Undefined SCPI header"')

    def query(self, command):
        if command == "*IDN?":
            return "KEITHLEY INSTRUMENTS,MODEL 2450,1234567,1.0"
        if command == "*LANG?":
            return self.language
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
        )
    )

    assert smu.current_limit_command == ":SOUR:VOLT:ILIMIT {value}"
    assert ":ROUT:TERM FRONT" in smu.inst.commands
    assert ":SENS:CURR:NPLC 1.0" in smu.inst.commands
    assert ":SOUR:VOLT:RANG 0.2" in smu.inst.commands
    assert ":SENS:CURR:RANG 0.0002" in smu.inst.commands
    assert ":SOUR:VOLT:ILIMIT 0.0002" in smu.inst.commands
    assert not any(command.startswith(":FORM:ELEM") for command in smu.inst.commands)


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
