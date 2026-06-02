import json
import zipfile
from pathlib import Path

from pytransport.feedback_bundle import create_feedback_bundle
from pytransport.instruments.fake import FakeSMU
from pytransport.recipes import DrainIVRecipe, SafetyPreset
from pytransport.runner import run_drain_iv


def make_recipe(output_dir: Path) -> DrainIVRecipe:
    return DrainIVRecipe.model_validate(
        {
            "measurement_name": "feedback_bundle_test",
            "safety_preset": "test_safe",
            "experiment": {"sample_id": "sample", "device_id": "device", "tags": ["feedback"]},
            "instrument": {"id": "keithley_2450", "address": "GPIB0::2::INSTR", "voltage_range_v": 0.1, "current_range_a": 1e-4},
            "sweep": {
                "mode": "linear_one_way",
                "start_v": -0.01,
                "stop_v": 0.01,
                "points": 3,
                "delay_s": 0.0,
                "current_compliance_a": 1e-4,
            },
            "output": {"directory": str(output_dir)},
            "checks": {"require_completed": True, "min_points": 3},
        }
    )


def make_safety() -> SafetyPreset:
    return SafetyPreset(
        name="test_safe",
        max_abs_voltage_v=0.2,
        max_abs_current_a=1e-3,
        default_current_compliance_a=1e-4,
    )


def test_create_feedback_bundle_includes_run_context(tmp_path):
    metadata = run_drain_iv(make_recipe(tmp_path), make_safety(), FakeSMU(resistance_ohm=1000, noise_std_a=0))
    run_dir = Path(metadata["run_dir"])

    paths = create_feedback_bundle(run_dir, output_dir=tmp_path / "feedback")

    assert paths.bundle_dir.exists()
    assert paths.zip_path.exists()
    assert (paths.bundle_dir / "run" / "metadata.json").exists()
    assert (paths.bundle_dir / "run" / "points.csv").exists()
    assert (paths.bundle_dir / "inspection.txt").exists()
    assert (paths.bundle_dir / "environment.json").exists()
    assert (paths.bundle_dir / "quality.txt").exists()

    manifest = json.loads(paths.manifest_path.read_text(encoding="utf-8"))
    assert manifest["measurement_name"] == "feedback_bundle_test"
    assert manifest["completed"] is True
    assert manifest["included"]["points"] is True
    assert any(record["path"] == "run/points.csv" for record in manifest["files"])

    with zipfile.ZipFile(paths.zip_path) as archive:
        assert "bundle_manifest.json" in archive.namelist()
        assert "run/metadata.json" in archive.namelist()


def test_create_feedback_bundle_can_exclude_large_artifacts(tmp_path):
    metadata = run_drain_iv(make_recipe(tmp_path), make_safety(), FakeSMU(resistance_ohm=1000, noise_std_a=0))
    run_dir = Path(metadata["run_dir"])

    paths = create_feedback_bundle(run_dir, output_dir=tmp_path / "feedback", include_points=False)

    assert not (paths.bundle_dir / "run" / "points.csv").exists()
    manifest = json.loads(paths.manifest_path.read_text(encoding="utf-8"))
    assert manifest["included"]["points"] is False
