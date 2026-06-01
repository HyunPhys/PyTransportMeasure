import pytest

from pytransport.cli import build_fake_smu, confirm_hardware_run, should_confirm_hardware_run


def test_hardware_run_requires_confirmation_by_default():
    assert should_confirm_hardware_run(dry_run=False, yes=False) is True


def test_dry_run_and_yes_skip_confirmation():
    assert should_confirm_hardware_run(dry_run=True, yes=False) is False
    assert should_confirm_hardware_run(dry_run=False, yes=True) is False


def test_confirm_hardware_run_accepts_only_explicit_yes():
    assert confirm_hardware_run(lambda prompt: "y") is True
    assert confirm_hardware_run(lambda prompt: "YES") is True
    assert confirm_hardware_run(lambda prompt: "") is False
    assert confirm_hardware_run(lambda prompt: "no") is False


def test_build_fake_smu_records_simulation_parameters():
    smu = build_fake_smu(1000, 0)
    probe = smu.probe()

    assert smu.resistance_ohm == 1000
    assert smu.noise_std_a == 0
    assert probe["simulated_resistance_ohm"] == "1000"
    assert probe["noise_std_a"] == "0"


def test_build_fake_smu_rejects_invalid_parameters():
    with pytest.raises(ValueError):
        build_fake_smu(0, 0)
    with pytest.raises(ValueError):
        build_fake_smu(1000, -1)
