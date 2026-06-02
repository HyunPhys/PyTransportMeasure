"""Lab laptop environment diagnostics."""

from __future__ import annotations

import importlib.metadata
import json
import platform
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from . import __version__
from .preflight import probe_keithley
from .visa_utils import list_resources


@dataclass(frozen=True)
class DoctorReport:
    pytransport_version: str
    python: str
    platform: str
    pyvisa_version: str | None
    pyvisa_error: str | None
    visa_resources: tuple[str, ...]
    visa_error: str | None
    requested_address: str | None
    address_found: bool | None
    probe: dict[str, str] | None
    probe_error: str | None

    @property
    def ok(self) -> bool:
        if self.pyvisa_error or self.visa_error:
            return False
        if self.requested_address is None:
            return True
        return bool(self.address_found and self.probe is not None and self.probe_error is None)


def run_doctor(
    address: str | None = None,
    timeout_ms: int = 10000,
    resource_lister: Callable[[], tuple[str, ...]] = list_resources,
    probe_factory: Callable[[str, int], dict[str, str]] | None = None,
) -> DoctorReport:
    pyvisa_version, pyvisa_error = get_pyvisa_version()
    resources: tuple[str, ...] = ()
    visa_error = None
    try:
        resources = resource_lister()
    except Exception as exc:
        visa_error = f"{type(exc).__name__}: {exc}"

    address_found = None if address is None else address in resources
    probe = None
    probe_error = None
    if address and address_found:
        try:
            if probe_factory is None:
                probe = probe_keithley(address, timeout_ms)
            else:
                probe = probe_factory(address, timeout_ms)
        except Exception as exc:
            probe_error = f"{type(exc).__name__}: {exc}"

    return DoctorReport(
        pytransport_version=__version__,
        python=sys.version,
        platform=platform.platform(),
        pyvisa_version=pyvisa_version,
        pyvisa_error=pyvisa_error,
        visa_resources=resources,
        visa_error=visa_error,
        requested_address=address,
        address_found=address_found,
        probe=probe,
        probe_error=probe_error,
    )


def get_pyvisa_version() -> tuple[str | None, str | None]:
    try:
        return importlib.metadata.version("pyvisa"), None
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"


def doctor_report_to_dict(report: DoctorReport) -> dict:
    return {
        "ok": report.ok,
        "pytransport_version": report.pytransport_version,
        "python": report.python,
        "platform": report.platform,
        "pyvisa_version": report.pyvisa_version,
        "pyvisa_error": report.pyvisa_error,
        "visa_resources": list(report.visa_resources),
        "visa_error": report.visa_error,
        "requested_address": report.requested_address,
        "address_found": report.address_found,
        "probe": report.probe,
        "probe_error": report.probe_error,
    }


def format_doctor_report(report: DoctorReport) -> str:
    lines = [
        "PyTransportMeasure Doctor",
        "",
        f"OK: {report.ok}",
        f"PyTransportMeasure: {report.pytransport_version}",
        f"Python: {report.python.splitlines()[0]}",
        f"Platform: {report.platform}",
        f"PyVISA: {report.pyvisa_version or 'n/a'}",
    ]
    if report.pyvisa_error:
        lines.append(f"PyVISA error: {report.pyvisa_error}")
    lines.extend(["", "VISA resources:"])
    if report.visa_resources:
        lines.extend(f"- {resource}" for resource in report.visa_resources)
    elif report.visa_error:
        lines.append(f"- error: {report.visa_error}")
    else:
        lines.append("- none")

    if report.requested_address is not None:
        lines.extend(
            [
                "",
                f"Requested address: {report.requested_address}",
                f"Address found: {report.address_found}",
                "Probe:",
            ]
        )
        if report.probe is not None:
            lines.extend(f"- {key}: {value}" for key, value in report.probe.items())
        elif report.probe_error is not None:
            lines.append(f"- error: {report.probe_error}")
        else:
            lines.append("- skipped")
    return "\n".join(lines)


def write_doctor_report(report: DoctorReport, output: str | Path, as_json: bool = False) -> Path:
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    if as_json:
        path.write_text(json.dumps(doctor_report_to_dict(report), indent=2, sort_keys=True), encoding="utf-8")
    else:
        path.write_text(format_doctor_report(report), encoding="utf-8")
    return path
