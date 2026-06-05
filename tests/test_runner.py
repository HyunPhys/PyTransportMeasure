import json

from pytransport.instruments.fake import FakeSMU
from pytransport.recipes import DrainIVRecipe, SafetyPreset
from pytransport.runner import run_drain_iv


class InterruptingSMU(FakeSMU):
    def __init__(self):
        super().__init__(noise_std_a=0)
        self.measure_count = 0

    def measure_current(self):
        self.measure_count += 1
        if self.measure_count == 2:
            raise KeyboardInterrupt()
        return super().measure_current()


class NplcMismatchSMU(FakeSMU):
    def output_on(self) -> None:
        raise AssertionError("output_on should not be called after readback mismatch")

    def read_voltage_source_config(self):
        readback = super().read_voltage_source_config()
        readback["current_nplc"] = "0.01"
        return readback


def make_recipe(tmp_path, compliance=1e-6):
    return DrainIVRecipe.model_validate(
        {
            "measurement_name": "dry_run_test",
            "instrument": {"address": "FAKE"},
            "sweep": {
                "start_v": -0.01,
                "stop_v": 0.01,
                "points": 5,
                "delay_s": 0,
                "current_compliance_a": compliance,
            },
            "output": {"directory": str(tmp_path)},
        }
    )


def make_safety(max_current=1e-6):
    return SafetyPreset(
        name="nano_device_safe",
        max_abs_voltage_v=1.0,
        max_abs_current_a=max_current,
        default_current_compliance_a=1e-7,
    )


def test_fake_smu_dry_run_writes_csv_and_metadata(tmp_path):
    recipe = make_recipe(tmp_path)
    progress = []
    metadata = run_drain_iv(
        recipe,
        make_safety(),
        FakeSMU(noise_std_a=0),
        recipe_path="recipe.yaml",
        progress_callback=lambda point, total: progress.append((point.index, total)),
    )

    assert metadata["completed"] is True
    assert metadata["points_written"] == 5
    assert progress == [(0, 5), (1, 5), (2, 5), (3, 5), (4, 5)]
    assert metadata["recipe_path"] == "recipe.yaml"
    assert metadata["run_dir"]
    assert metadata["metadata_path"]
    assert metadata["instrument_probe"]["language"] == "SIM"
    assert metadata["configured_smu"]["current_compliance_a"] == 1e-6
    assert metadata["configured_smu"]["nplc"] is None
    assert metadata["configured_smu_readback"]["source_current_limit"] == "1e-06"
    assert metadata["output_state"]["instrument"]["off_after_run"] is True
    assert metadata["output_state"]["instrument"]["zero_before_off_succeeded"] is True
    csv_path = tmp_path / next(tmp_path.iterdir()).name / "points.csv"
    metadata_path = csv_path.with_name("metadata.json")
    assert csv_path.exists()
    assert metadata_path.exists()
    assert (csv_path.parent / "recipe_snapshot.yaml").exists()
    assert (csv_path.parent / "safety_snapshot.yaml").exists()
    saved = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert saved["completed"] is True
    assert saved["recipe"]["experiment"]["tags"] == []
    assert saved["configured_smu"]["current_compliance_a"] == 1e-6
    assert saved["configured_smu_readback"]["source_function"] == "VOLT"
    assert saved["output_state"]["instrument"]["enabled"] is False
    assert saved["output_state"]["instrument"]["zero_before_off_target_v"] == 0.0
    assert saved["recipe_snapshot_path"].endswith("recipe_snapshot.yaml")
    assert saved["safety_snapshot_path"].endswith("safety_snapshot.yaml")


def test_partial_save_on_current_limit(tmp_path):
    metadata = run_drain_iv(
        make_recipe(tmp_path, compliance=1e-9),
        make_safety(max_current=1e-6),
        FakeSMU(resistance_ohm=1.0, noise_std_a=0),
    )

    assert metadata["completed"] is False
    assert metadata["error_type"] == "SafetyLimitError"
    assert metadata["triggered_limit"] in {"measured_current_a", "instrument_compliance"}
    run_dir = next(tmp_path.iterdir())
    assert (run_dir / "points.csv").exists()
    assert (run_dir / "metadata.json").exists()


def test_keyboard_interrupt_saves_partial_and_turns_output_off(tmp_path):
    smu = InterruptingSMU()
    metadata = run_drain_iv(make_recipe(tmp_path), make_safety(), smu)

    assert metadata["completed"] is False
    assert metadata["interrupted"] is True
    assert metadata["error_type"] == "KeyboardInterrupt"
    assert metadata["points_written"] == 1
    assert smu.is_output_on is False
    run_dir = next(tmp_path.iterdir())
    saved = json.loads((run_dir / "metadata.json").read_text(encoding="utf-8"))
    assert saved["interrupted"] is True
    assert saved["points_written"] == 1


def test_stop_request_saves_partial_and_turns_output_off(tmp_path):
    smu = FakeSMU(noise_std_a=0)
    progress = []

    metadata = run_drain_iv(
        make_recipe(tmp_path),
        make_safety(),
        smu,
        progress_callback=lambda point, total: progress.append(point.index),
        stop_requested=lambda: len(progress) >= 2,
    )

    assert metadata["completed"] is False
    assert metadata["interrupted"] is True
    assert metadata["error_type"] == "KeyboardInterrupt"
    assert metadata["points_written"] == 2
    assert smu.is_output_on is False
    run_dir = next(tmp_path.iterdir())
    saved = json.loads((run_dir / "metadata.json").read_text(encoding="utf-8"))
    assert saved["interrupted"] is True
    assert saved["points_written"] == 2


def test_smu_readback_mismatch_stops_before_output_on(tmp_path):
    data = {
        "measurement_name": "readback_mismatch",
        "instrument": {"address": "FAKE", "nplc": 1.0},
        "sweep": {
            "start_v": 0,
            "stop_v": 0.01,
            "points": 2,
            "delay_s": 0,
            "current_compliance_a": 1e-6,
        },
        "output": {"directory": str(tmp_path)},
    }
    recipe = DrainIVRecipe.model_validate(data)
    smu = NplcMismatchSMU(noise_std_a=0)

    metadata = run_drain_iv(recipe, make_safety(), smu)

    assert metadata["completed"] is False
    assert metadata["error_type"] == "SafetyLimitError"
    assert metadata["triggered_limit"] == "instrument_smu_config_readback"
    assert smu.is_output_on is False
    saved = json.loads((next(tmp_path.iterdir()) / "metadata.json").read_text(encoding="utf-8"))
    assert saved["configured_smu_readback_check"]["matched"] is False
    assert saved["output_state"]["instrument"]["output_on_attempted"] is False
    assert saved["output_state"]["instrument"]["off_after_run"] is True
    assert saved["output_state"]["instrument"]["zero_before_off_succeeded"] is True
