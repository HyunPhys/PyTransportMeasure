"""Keithley 2450 SMU driver for conservative Drain I-V sweeps."""

from __future__ import annotations

from .base import SMUVoltageSourceConfig


class Keithley2450:
    def __init__(self, address: str, timeout_ms: int = 10000):
        self.address = address
        self.timeout_ms = timeout_ms
        self._rm = None
        self._inst = None
        self.current_limit_command: str | None = None

    def connect(self) -> None:
        import pyvisa

        self._rm = pyvisa.ResourceManager()
        self._inst = self._rm.open_resource(self.address)
        self._inst.timeout = self.timeout_ms
        self._inst.write_termination = "\n"
        self._inst.read_termination = "\n"

    @property
    def inst(self):
        if self._inst is None:
            raise RuntimeError("Keithley2450 is not connected")
        return self._inst

    def identify(self) -> str:
        return str(self.inst.query("*IDN?")).strip()

    def language(self) -> str:
        return str(self.inst.query("*LANG?")).strip().upper()

    def system_error(self) -> str:
        return self._query_error()

    def probe(self) -> dict[str, str]:
        return {
            "address": self.address,
            "idn": self.identify(),
            "language": self.language(),
            "system_error": self.system_error(),
        }

    @staticmethod
    def _is_no_error(response: str) -> bool:
        return response.startswith("0,") or response.upper().startswith("+0,")

    def _query_error(self) -> str:
        response = str(self.inst.query(":SYST:ERR?")).strip()
        return response

    def _raise_on_error(self, context: str) -> None:
        response = self._query_error()
        if self._is_no_error(response):
            return
        raise RuntimeError(f"Keithley 2450 error after {context}: {response}")

    def _write_checked(self, command: str, context: str) -> None:
        self.inst.write(command)
        self._raise_on_error(context)

    def _query_optional(self, command: str) -> str:
        try:
            response = str(self.inst.query(command)).strip()
            error = self._query_error()
            if self._is_no_error(error):
                return response
            self.inst.write("*CLS")
            return f"ERROR after {command}: {error}"
        except Exception as exc:
            try:
                self.inst.write("*CLS")
            except Exception:
                pass
            return f"ERROR during {command}: {type(exc).__name__}: {exc}"

    def _set_current_limit(self, current_compliance_a: float) -> None:
        candidates = [
            ":SOUR:VOLT:ILIM {value}",
            ":SOUR:VOLT:ILIMIT {value}",
        ]
        errors: list[str] = []
        for template in candidates:
            command = template.format(value=current_compliance_a)
            self.inst.write(command)
            response = self._query_error()
            if self._is_no_error(response):
                self.current_limit_command = template
                return
            errors.append(f"{command} -> {response}")
            self.inst.write("*CLS")
        joined_errors = "; ".join(errors)
        raise RuntimeError(f"Keithley 2450 did not accept any current limit command: {joined_errors}")

    def configure_current_remote_sense(self, enabled: bool) -> None:
        language = self.language()
        if language != "SCPI":
            raise RuntimeError(f"Keithley 2450 command set must be SCPI for current remote sense, got {language!r}")
        state = "ON" if enabled else "OFF"
        self._write_checked(f":SENS:CURR:RSEN {state}", "current remote-sense configuration")

    def read_current_remote_sense(self) -> str:
        return self._query_optional(":SENS:CURR:RSEN?")

    def configure_voltage_source(self, config: SMUVoltageSourceConfig) -> None:
        self.inst.write("*RST")
        self.inst.write("*CLS")
        language = self.language()
        if language != "SCPI":
            raise RuntimeError(f"Keithley 2450 command set must be SCPI for v0, got {language!r}")
        if config.terminal is not None:
            self._write_checked(f":ROUT:TERM {config.terminal}", "terminal selection")
        self._write_checked(":SENS:FUNC \"CURR\"", "sense function configuration")
        if config.nplc is not None:
            self._write_checked(f":SENS:CURR:NPLC {config.nplc}", "current NPLC configuration")
        if config.current_range_a is None:
            self._write_checked(":SENS:CURR:RANG:AUTO ON", "current range configuration")
        else:
            self._write_checked(f":SENS:CURR:RANG {config.current_range_a}", "current range configuration")
        self._write_checked(":SOUR:FUNC VOLT", "source function configuration")
        if config.voltage_range_v is not None:
            self._write_checked(f":SOUR:VOLT:RANG {config.voltage_range_v}", "voltage range configuration")
        if config.source_delay_s is not None:
            self._write_checked(f":SOUR:VOLT:DEL {config.source_delay_s}", "voltage source delay configuration")
        self._write_checked(":SOUR:VOLT:READ:BACK ON", "voltage readback configuration")
        self._set_current_limit(config.current_compliance_a)
        self._write_checked(":SOUR:VOLT 0", "initial voltage configuration")

    def read_voltage_source_config(self) -> dict[str, str | None]:
        current_limit_query = None
        if self.current_limit_command is not None:
            current_limit_query = self.current_limit_command.split(" {value}", maxsplit=1)[0] + "?"
        return {
            "source_function": self._query_optional(":SOUR:FUNC?"),
            "sense_function": self._query_optional(":SENS:FUNC?"),
            "terminal": self._query_optional(":ROUT:TERM?"),
            "current_nplc": self._query_optional(":SENS:CURR:NPLC?"),
            "current_range": self._query_optional(":SENS:CURR:RANG?"),
            "current_range_auto": self._query_optional(":SENS:CURR:RANG:AUTO?"),
            "voltage_range": self._query_optional(":SOUR:VOLT:RANG?"),
            "source_delay": self._query_optional(":SOUR:VOLT:DEL?"),
            "voltage_readback": self._query_optional(":SOUR:VOLT:READ:BACK?"),
            "source_current_limit": None if current_limit_query is None else self._query_optional(current_limit_query),
            "source_current_limit_query": current_limit_query,
        }

    def set_voltage(self, voltage_v: float) -> None:
        self.inst.write(f":SOUR:VOLT {voltage_v}")

    def measure_current(self) -> tuple[float, bool]:
        response = str(self.inst.query(":READ?")).strip()
        parts = [part.strip() for part in response.split(",")]
        current_a = float(parts[0])
        status_text = ",".join(parts[2:]).upper() if len(parts) > 2 else ""
        compliance_hit = "COMP" in status_text
        return current_a, compliance_hit

    def output_on(self) -> None:
        self.inst.write(":OUTP ON")

    def output_off(self) -> None:
        if self._inst is not None:
            try:
                self._inst.write(":SOUR:VOLT 0")
            finally:
                self._inst.write(":OUTP OFF")

    def close(self) -> None:
        try:
            self.output_off()
        finally:
            if self._inst is not None:
                self._inst.close()
                self._inst = None
            if self._rm is not None:
                self._rm.close()
                self._rm = None
