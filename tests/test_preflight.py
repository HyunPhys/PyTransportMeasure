from pytransport.preflight import (
    format_ac_lockin_preflight_report,
    format_dual_gate_lockin_preflight_report,
    format_preflight_report,
    format_single_gate_preflight_report,
    run_ac_lockin_preflight,
    run_dual_gate_lockin_preflight,
    run_preflight,
    run_single_gate_preflight,
)


LOCKIN_SETTING_PROBE = {
    "setting_reference_source": "0",
    "setting_reference_frequency_hz": "17.777",
    "setting_sine_output_amplitude_v": "0.01",
    "setting_input_mode": "0",
    "setting_voltage_input": "0",
    "setting_input_coupling": "0",
    "setting_input_grounding": "0",
    "setting_voltage_input_range_v": "4",
    "setting_sensitivity_index": "18",
    "setting_time_constant_index": "10",
    "setting_filter_slope_index": "3",
    "setting_synchronous_filter": "0",
}


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


def test_run_ac_lockin_preflight_ok():
    source_probed = []
    lockin_probed = []

    def source_probe(address, timeout):
        source_probed.append((address, timeout))
        return {
            "address": address,
            "idn": "KEITHLEY INSTRUMENTS,MODEL 2450,123,1.0",
            "language": "SCPI",
            "system_error": '0,"No error"',
        }

    def lockin_probe(address, timeout):
        lockin_probed.append((address, timeout))
        return {
            "address": address,
            "idn": "Stanford_Research_Systems,SR860,000111,v1.23",
            "error_status": "0",
            "lia_status": "0",
            **LOCKIN_SETTING_PROBE,
        }

    report = run_ac_lockin_preflight(
        "configs/recipes/ac_lockin_dry_run.yaml",
        resource_lister=lambda: ("GPIB0::2::INSTR", "GPIB0::4::INSTR"),
        source_probe_factory=source_probe,
        lockin_probe_factory=lockin_probe,
    )

    text = format_ac_lockin_preflight_report(report)

    assert report.ok is True
    assert report.source.ok is True
    assert report.lockin.ok is True
    assert all(check.ok for check in report.lockin_settings)
    assert source_probed == [("GPIB0::2::INSTR", 10000)]
    assert lockin_probed == [("GPIB0::4::INSTR", 10000)]
    assert "Source/lock-in addresses distinct: True" in text
    assert "Lock-in setting check:" in text
    assert "all expected settings match: True" in text
    assert "AC lock-in preflight OK: True" in text


def test_run_ac_lockin_preflight_fails_when_expected_lockin_setting_mismatches():
    bad_settings = {**LOCKIN_SETTING_PROBE, "setting_reference_frequency_hz": "1000"}

    report = run_ac_lockin_preflight(
        "configs/recipes/ac_lockin_dry_run.yaml",
        resource_lister=lambda: ("GPIB0::2::INSTR", "GPIB0::4::INSTR"),
        source_probe_factory=lambda address, timeout: {
            "address": address,
            "idn": "KEITHLEY INSTRUMENTS,MODEL 2450,123,1.0",
            "language": "SCPI",
            "system_error": '0,"No error"',
        },
        lockin_probe_factory=lambda address, timeout: {
            "address": address,
            "idn": "Stanford_Research_Systems,SR860,000111,v1.23",
            "error_status": "0",
            "lia_status": "0",
            **bad_settings,
        },
    )

    text = format_ac_lockin_preflight_report(report)

    assert report.ok is False
    assert any(check.field == "reference_frequency_hz" and not check.ok for check in report.lockin_settings)
    assert "reference_frequency_hz: expected 17.777, actual 1000, ok: False" in text
    assert "AC lock-in preflight OK: False" in text


def test_run_ac_lockin_preflight_fails_when_lockin_address_missing():
    report = run_ac_lockin_preflight(
        "configs/recipes/ac_lockin_dry_run.yaml",
        resource_lister=lambda: ("GPIB0::2::INSTR",),
        source_probe_factory=lambda address, timeout: {
            "address": address,
            "idn": "KEITHLEY INSTRUMENTS,MODEL 2450,123,1.0",
            "language": "SCPI",
            "system_error": '0,"No error"',
        },
        lockin_probe_factory=lambda address, timeout: {},
    )

    text = format_ac_lockin_preflight_report(report)

    assert report.ok is False
    assert report.source.ok is True
    assert report.lockin.ok is False
    assert "Lock-in instrument:" in text
    assert "- address found: False" in text
    assert "AC lock-in preflight OK: False" in text


def test_run_dual_gate_lockin_preflight_ok():
    gate_probed = []
    lockin_probed = []

    def gate_probe(address, timeout):
        gate_probed.append((address, timeout))
        return {
            "address": address,
            "idn": f"KEITHLEY INSTRUMENTS,MODEL 2450,{address},1.0",
            "language": "SCPI",
            "system_error": '0,"No error"',
        }

    def lockin_probe(address, timeout):
        lockin_probed.append((address, timeout))
        return {
            "address": address,
            "idn": "Stanford_Research_Systems,SR860,000111,v1.23",
            "error_status": "0",
            "lia_status": "0",
            **LOCKIN_SETTING_PROBE,
        }

    report = run_dual_gate_lockin_preflight(
        "configs/recipes/dual_gate_lockin_dry_run.yaml",
        resource_lister=lambda: ("GPIB0::2::INSTR", "GPIB0::3::INSTR", "GPIB0::4::INSTR"),
        gate_probe_factory=gate_probe,
        lockin_probe_factory=lockin_probe,
    )

    text = format_dual_gate_lockin_preflight_report(report)

    assert report.ok is True
    assert report.gate1.ok is True
    assert report.gate2.ok is True
    assert report.lockin.ok is True
    assert all(check.ok for check in report.lockin_settings)
    assert gate_probed == [("GPIB0::2::INSTR", 10000), ("GPIB0::3::INSTR", 10000)]
    assert lockin_probed == [("GPIB0::4::INSTR", 10000)]
    assert "Topology:" in text
    assert "- Source/drain: S -> D" in text
    assert "Scan readiness:" in text
    assert "- Gate grid: 5 x 5 = 25 points" in text
    assert "- Within default point guard: False" in text
    assert "Gate1/gate2/lock-in addresses distinct: True" in text
    assert "all expected settings match: True" in text
    assert "Dual-gate lock-in preflight OK: True" in text


def test_run_dual_gate_lockin_preflight_fails_when_lockin_address_missing():
    report = run_dual_gate_lockin_preflight(
        "configs/recipes/dual_gate_lockin_dry_run.yaml",
        resource_lister=lambda: ("GPIB0::2::INSTR", "GPIB0::3::INSTR"),
        gate_probe_factory=lambda address, timeout: {
            "address": address,
            "idn": "KEITHLEY INSTRUMENTS,MODEL 2450,123,1.0",
            "language": "SCPI",
            "system_error": '0,"No error"',
        },
        lockin_probe_factory=lambda address, timeout: {},
    )

    text = format_dual_gate_lockin_preflight_report(report)

    assert report.ok is False
    assert report.gate1.ok is True
    assert report.gate2.ok is True
    assert report.lockin.ok is False
    assert "Lock-in instrument:" in text
    assert "- address found: False" in text
    assert "Dual-gate lock-in preflight OK: False" in text
