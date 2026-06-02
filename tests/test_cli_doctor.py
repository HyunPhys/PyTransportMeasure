from pytransport import cli
from pytransport.doctor import run_doctor as real_run_doctor


def test_cli_doctor_writes_json_report(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "run_doctor", lambda address=None, timeout_ms=10000: real_run_doctor(resource_lister=lambda: ()))

    output = tmp_path / "doctor.json"
    code = cli.main(["doctor", "--json", "--output", str(output)])

    assert code == 0
    assert output.exists()
    assert '"ok": true' in output.read_text(encoding="utf-8")
