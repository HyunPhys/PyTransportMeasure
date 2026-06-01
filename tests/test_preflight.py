from pytransport.preflight import format_preflight_report, run_preflight


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
