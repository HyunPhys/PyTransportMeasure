import json

from pytransport.doctor import doctor_report_to_dict, format_doctor_report, run_doctor, write_doctor_report


def test_doctor_reports_resources_and_probe_when_address_found():
    report = run_doctor(
        address="GPIB0::2::INSTR",
        resource_lister=lambda: ("ASRL1::INSTR", "GPIB0::2::INSTR"),
        probe_factory=lambda address, timeout: {
            "address": address,
            "idn": "KEITHLEY INSTRUMENTS,MODEL 2450,123,1.0",
            "language": "SCPI",
            "system_error": '0,"No error"',
        },
    )

    text = format_doctor_report(report)

    assert report.ok is True
    assert "GPIB0::2::INSTR" in text
    assert "Address found: True" in text
    assert "MODEL 2450" in text
    assert doctor_report_to_dict(report)["ok"] is True


def test_doctor_fails_when_address_missing():
    report = run_doctor(
        address="GPIB0::2::INSTR",
        resource_lister=lambda: ("ASRL1::INSTR",),
        probe_factory=lambda address, timeout: {},
    )

    text = format_doctor_report(report)

    assert report.ok is False
    assert "Address found: False" in text
    assert "- skipped" in text


def test_doctor_captures_resource_listing_error():
    def fail_resources():
        raise RuntimeError("VISA backend missing")

    report = run_doctor(resource_lister=fail_resources)

    assert report.ok is False
    assert "VISA backend missing" in format_doctor_report(report)


def test_write_doctor_report_json(tmp_path):
    report = run_doctor(resource_lister=lambda: ("GPIB0::2::INSTR",))
    output = write_doctor_report(report, tmp_path / "doctor.json", as_json=True)

    data = json.loads(output.read_text(encoding="utf-8"))
    assert data["visa_resources"] == ["GPIB0::2::INSTR"]
