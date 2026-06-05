from pytransport import cli
from pytransport.doctor import run_doctor as real_run_doctor


def test_cli_doctor_writes_json_report(tmp_path, monkeypatch):
    monkeypatch.setattr(
        cli,
        "run_doctor",
        lambda address=None, timeout_ms=10000, probe_factory=None: real_run_doctor(resource_lister=lambda: ()),
    )

    output = tmp_path / "doctor.json"
    code = cli.main(["doctor", "--json", "--output", str(output)])

    assert code == 0
    assert output.exists()
    assert '"ok": true' in output.read_text(encoding="utf-8")


class FakeCliInstrument:
    def __init__(self, address, timeout_ms):
        self.address = address
        self.timeout_ms = timeout_ms
        self.connected = False

    def connect(self):
        self.connected = True

    def identify(self):
        return f"FAKE,{self.address},{self.timeout_ms}"

    def probe(self):
        return {"address": self.address, "idn": self.identify(), "error_status": "0", "lia_status": "0"}

    def close(self):
        self.connected = False


def test_cli_identify_accepts_srs_sr860(monkeypatch, capsys):
    monkeypatch.setattr(cli, "open_supported_instrument", lambda instrument, address, timeout: FakeCliInstrument(address, timeout))

    code = cli.main(["identify", "--instrument", "srs_sr860", "--address", "GPIB0::4::INSTR", "--timeout-ms", "1234"])

    assert code == 0
    assert "FAKE,GPIB0::4::INSTR,1234" in capsys.readouterr().out


def test_cli_probe_accepts_srs_sr860(monkeypatch, capsys):
    monkeypatch.setattr(cli, "open_supported_instrument", lambda instrument, address, timeout: FakeCliInstrument(address, timeout))

    code = cli.main(["probe", "--instrument", "srs_sr860", "--address", "GPIB0::4::INSTR"])

    assert code == 0
    output = capsys.readouterr().out
    assert "address: GPIB0::4::INSTR" in output
    assert "lia_status: 0" in output
