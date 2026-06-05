from pytransport.preflight import (
    format_preflight_report,
    format_single_gate_preflight_report,
    run_preflight,
    run_single_gate_preflight,
)


def test_run_preflight_ok():
    report = run_preflight(
        "configs/recipes/drain_iv_1k_resistor.yaml",
        resource_lister=lambda: ("GPIB0::2::INSTR",),
        probe_factory=lambda address, timeout: {
            "address": address,
            "idn": "KEITHLEY INSTRUMENTS,MODEL 2450,123,1.0",
            "language": "SCPI",
            "system_error": '0,"No error"',
        },
    )

    text = format_preflight_report(report)

    assert report.ok is True
    assert "Preflight OK: True" in text
    assert "Recipe address found: True" in text


def test_run_preflight_fails_when_address_missing():
    report = run_preflight(
        "configs/recipes/drain_iv_1k_resistor.yaml",
        resource_lister=lambda: ("ASRL1::INSTR",),
        probe_factory=lambda address, timeout: {},
    )

    text = format_preflight_report(report)

    assert report.ok is False
    assert "Recipe address found: False" in text
    assert "Probe:" in text
    assert "- skipped" in text


def test_run_single_gate_preflight_ok():
    probed = []

    def probe(address, timeout):
        probed.append((address, timeout))
        return {
            "address": address,
            "idn": f"KEITHLEY INSTRUMENTS,MODEL 2450,{address},1.0",
            "language": "SCPI",
            "system_error": '0,"No error"',
        }

    report = run_single_gate_preflight(
        "configs/recipes/single_gate_hardware_smoke.yaml",
        resource_lister=lambda: ("GPIB0::2::INSTR", "GPIB0::3::INSTR"),
        probe_factory=probe,
    )

    text = format_single_gate_preflight_report(report)

    assert report.ok is True
    assert report.drain.ok is True
    assert report.gate.ok is True
    assert probed == [("GPIB0::2::INSTR", 10000), ("GPIB0::3::INSTR", 10000)]
    assert "Drain/gate addresses distinct: True" in text
    assert "Single-gate preflight OK: True" in text


def test_run_single_gate_preflight_fails_when_gate_address_missing():
    report = run_single_gate_preflight(
        "configs/recipes/single_gate_hardware_smoke.yaml",
        resource_lister=lambda: ("GPIB0::2::INSTR",),
        probe_factory=lambda address, timeout: {
            "address": address,
            "idn": "KEITHLEY INSTRUMENTS,MODEL 2450,123,1.0",
            "language": "SCPI",
            "system_error": '0,"No error"',
        },
    )

    text = format_single_gate_preflight_report(report)

    assert report.ok is False
    assert report.drain.ok is True
    assert report.gate.ok is False
    assert "Gate instrument:" in text
    assert "- address found: False" in text
    assert "Single-gate preflight OK: False" in text
