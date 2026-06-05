"""SRS SR860 lock-in amplifier driver.

The command subset here is intentionally small and based on the local
``SR860m.pdf`` manual: ``*IDN?``, ``ERRS?``, ``LIAS?``, ``SNAP?``, and
``OUTP?``. Measurement runners should grow around this driver only after the
hardware smoke tests pass.
"""

from __future__ import annotations

from .base import LockInReading


class SRS_SR860:
    def __init__(self, address: str, timeout_ms: int = 10000):
        self.address = address
        self.timeout_ms = timeout_ms
        self._rm = None
        self._inst = None

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
            raise RuntimeError("SRS_SR860 is not connected")
        return self._inst

    def identify(self) -> str:
        return str(self.inst.query("*IDN?")).strip()

    def error_status(self) -> str:
        return str(self.inst.query("ERRS?")).strip()

    def lia_status(self) -> str:
        return str(self.inst.query("LIAS?")).strip()

    def probe(self) -> dict[str, str]:
        return {
            "address": self.address,
            "idn": self.identify(),
            "error_status": self.error_status(),
            "lia_status": self.lia_status(),
        }

    def read_channels(self) -> LockInReading:
        x_v, y_v, r_v = self._query_snap_xyr()
        theta_deg = self._query_output("THeta")
        return LockInReading(x_v=x_v, y_v=y_v, r_v=r_v, theta_deg=theta_deg)

    def _query_snap_xyr(self) -> tuple[float, float, float]:
        response = str(self.inst.query("SNAP? X,Y,R")).strip()
        parts = [part.strip() for part in response.split(",")]
        if len(parts) != 3:
            raise RuntimeError(f"SR860 SNAP? X,Y,R returned {len(parts)} values: {response!r}")
        return float(parts[0]), float(parts[1]), float(parts[2])

    def _query_output(self, parameter: str) -> float:
        return float(str(self.inst.query(f"OUTP? {parameter}")).strip())

    def close(self) -> None:
        if self._inst is not None:
            self._inst.close()
            self._inst = None
        if self._rm is not None:
            self._rm.close()
            self._rm = None


def probe_srs_sr860(address: str, timeout_ms: int) -> dict[str, str]:
    lockin = SRS_SR860(address, timeout_ms)
    try:
        lockin.connect()
        return lockin.probe()
    finally:
        lockin.close()
