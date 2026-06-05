import json

from pytransport import cli
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
from pytransport.recipes import load_ac_lockin_recipe, load_dual_gate_lockin_recipe
from pytransport.sr860_config import review_sr860_config_commands


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


def write_matching_sr860_configure_json(recipe, path):
    review = review_sr860_config_commands(recipe)
    steps = [
        {
            "index": command["index"],
            "field": command["field"],
            "command": command["command"],
            "query": command["query"],
            "expected_readback": command["expected_readback"],
            "actual_readback": command["expected_readback"],
            "matched": True,
        }
        for command in review["commands"]
    ]
    payload = {
        "schema": "pytransport.sr860_configure.v1",
        "completed": True,
        "review": review,
        "apply": {"matched": True, "steps": steps},
        "hardware_approval_note": "test evidence",
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


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


def test_run_ac_lockin_preflight_can_require_sr860_configure_evidence(tmp_path):
    recipe_path = "configs/recipes/ac_lockin_hardware_smoke.yaml"
    configure_json = write_matching_sr860_configure_json(
        load_ac_lockin_recipe(recipe_path),
        tmp_path / "sr860_configure.json",
    )

    report = run_ac_lockin_preflight(
        recipe_path,
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
            **LOCKIN_SETTING_PROBE,
        },
        sr860_configure_json=configure_json,
    )

    text = format_ac_lockin_preflight_report(report)

    assert report.ok is True
    assert report.sr860_configure_evidence["ok"] is True
    assert "SR860 configure evidence check" in text
    assert "OK: True" in text


def test_run_ac_lockin_four_terminal_preflight_accepts_differential_voltage_input():
    differential_probe = {**LOCKIN_SETTING_PROBE, "setting_voltage_input": "1"}

    report = run_ac_lockin_preflight(
        "configs/recipes/ac_lockin_four_terminal_dry_run.yaml",
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
            **differential_probe,
        },
    )

    text = format_ac_lockin_preflight_report(report)

    assert report.ok is True
    assert all(check.ok for check in report.lockin_settings)
    assert "voltage_input: expected a-b, actual 1, ok: True" in text
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


def test_run_dual_gate_lockin_preflight_blocks_stale_sr860_configure_evidence(tmp_path):
    recipe_path = "configs/recipes/dual_gate_lockin_dry_run.yaml"
    configure_json = write_matching_sr860_configure_json(
        load_dual_gate_lockin_recipe(recipe_path),
        tmp_path / "sr860_configure.json",
    )
    payload = json.loads(configure_json.read_text(encoding="utf-8"))
    payload["apply"]["steps"][0]["actual_readback"] = "1"
    configure_json.write_text(json.dumps(payload), encoding="utf-8")

    report = run_dual_gate_lockin_preflight(
        recipe_path,
        resource_lister=lambda: ("GPIB0::2::INSTR", "GPIB0::3::INSTR", "GPIB0::4::INSTR"),
        gate_probe_factory=lambda address, timeout: {
            "address": address,
            "idn": f"KEITHLEY INSTRUMENTS,MODEL 2450,{address},1.0",
            "language": "SCPI",
            "system_error": '0,"No error"',
        },
        lockin_probe_factory=lambda address, timeout: {
            "address": address,
            "idn": "Stanford_Research_Systems,SR860,000111,v1.23",
            "error_status": "0",
            "lia_status": "0",
            **LOCKIN_SETTING_PROBE,
        },
        sr860_configure_json=configure_json,
    )

    text = format_dual_gate_lockin_preflight_report(report)

    assert report.ok is False
    assert report.sr860_configure_evidence["ok"] is False
    assert "SR860 configure evidence check" in text
    assert "apply_steps_match_recipe: FAIL" in text
    assert "Dual-gate lock-in preflight OK: False" in text


def test_cli_ac_lockin_preflight_passes_sr860_configure_json(monkeypatch, tmp_path):
    captured = {}

    def fake_preflight(recipe, safety_dir, sr860_configure_json=None):
        captured["recipe"] = recipe
        captured["safety_dir"] = safety_dir
        captured["sr860_configure_json"] = sr860_configure_json
        source = lockin = type(
            "FakeInstrument",
            (),
            {"ok": True, "label": "fake", "address": "FAKE", "address_found": True, "probe": {}, "probe_error": None},
        )()
        return type(
            "FakeReport",
            (),
            {
                "recipe_path": str(recipe),
                "validation_ok": True,
                "validation_error": None,
                "visa_resources": (),
                "distinct_addresses": True,
                "source": source,
                "lockin": lockin,
                "lockin_settings": (),
                "sr860_configure_evidence": {"ok": True, "checks": []},
                "ok": True,
            },
        )()

    monkeypatch.setattr(cli, "run_ac_lockin_preflight", fake_preflight)

    code = cli.main(
        [
            "ac-lockin-preflight",
            "configs/recipes/ac_lockin_hardware_smoke.yaml",
            "--sr860-configure-json",
            str(tmp_path / "sr860_configure.json"),
        ]
    )

    assert code == 0
    assert captured["sr860_configure_json"] == tmp_path / "sr860_configure.json"


def test_cli_dual_gate_lockin_preflight_passes_sr860_configure_json(monkeypatch, tmp_path):
    captured = {}

    def fake_preflight(recipe, safety_dir, sr860_configure_json=None):
        captured["recipe"] = recipe
        captured["safety_dir"] = safety_dir
        captured["sr860_configure_json"] = sr860_configure_json
        instrument = type(
            "FakeInstrument",
            (),
            {"ok": True, "label": "fake", "address": "FAKE", "address_found": True, "probe": {}, "probe_error": None},
        )()
        return type(
            "FakeReport",
            (),
            {
                "recipe_path": str(recipe),
                "validation_ok": True,
                "validation_error": None,
                "visa_resources": (),
                "distinct_addresses": True,
                "topology_lines": (),
                "scan_readiness_lines": (),
                "gate1": instrument,
                "gate2": instrument,
                "lockin": instrument,
                "lockin_settings": (),
                "sr860_configure_evidence": {"ok": True, "checks": []},
                "ok": True,
            },
        )()

    monkeypatch.setattr(cli, "run_dual_gate_lockin_preflight", fake_preflight)

    code = cli.main(
        [
            "dual-gate-lockin-preflight",
            "configs/recipes/dual_gate_lockin_dry_run.yaml",
            "--sr860-configure-json",
            str(tmp_path / "sr860_configure.json"),
        ]
    )

    assert code == 0
    assert captured["sr860_configure_json"] == tmp_path / "sr860_configure.json"


def test_run_dual_gate_lockin_four_terminal_preflight_accepts_differential_voltage_input():
    differential_probe = {**LOCKIN_SETTING_PROBE, "setting_voltage_input": "1"}

    report = run_dual_gate_lockin_preflight(
        "configs/recipes/dual_gate_lockin_four_terminal_dry_run.yaml",
        resource_lister=lambda: ("GPIB0::2::INSTR", "GPIB0::3::INSTR", "GPIB0::4::INSTR"),
        gate_probe_factory=lambda address, timeout: {
            "address": address,
            "idn": f"KEITHLEY INSTRUMENTS,MODEL 2450,{address},1.0",
            "language": "SCPI",
            "system_error": '0,"No error"',
        },
        lockin_probe_factory=lambda address, timeout: {
            "address": address,
            "idn": "Stanford_Research_Systems,SR860,000111,v1.23",
            "error_status": "0",
            "lia_status": "0",
            **differential_probe,
        },
    )

    text = format_dual_gate_lockin_preflight_report(report)

    assert report.ok is True
    assert all(check.ok for check in report.lockin_settings)
    assert "voltage_input: expected a-b, actual 1, ok: True" in text
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
