import json

import yaml

from pytransport.dual_gate_lockin_hall_suite import (
    write_dual_gate_lockin_hall_suite_acquisition_package,
    write_dual_gate_lockin_hall_suite_template,
)
from pytransport.hall_workflow import (
    format_dual_gate_lockin_hall_suite_workflow_status,
    inspect_dual_gate_lockin_hall_suite_workflow_status,
    run_dual_gate_lockin_hall_suite_approved_next_scan_rehearsal,
)


def test_hall_workflow_status_reports_package_stage_readiness(tmp_path):
    package_dir = tmp_path / "package"
    recipes_dir = package_dir / "recipes"
    recipes_dir.mkdir(parents=True)
    recipe_paths = {}
    for key in ["longitudinal", "plus", "minus", "zero"]:
        recipe = recipes_dir / f"{key}.yaml"
        recipe.write_text("measurement_name: fake\n", encoding="utf-8")
        recipe_paths[key] = f"recipes/{recipe.name}"
    (package_dir / "acquisition_runbook.md").write_text("# runbook\n", encoding="utf-8")
    package_dir.with_suffix(".zip").write_bytes(b"fake zip placeholder")
    manifest = {
        "package_name": "fake_package",
        "copied_recipes": recipe_paths,
        "approved_next_scan": {"strategy": "refine_charge_neutrality_region"},
    }
    (package_dir / "package_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    payload = inspect_dual_gate_lockin_hall_suite_workflow_status(package_dir)
    text = format_dual_gate_lockin_hall_suite_workflow_status(payload)

    assert payload["ready_for_lab_review"] is True
    stage_by_key = {stage["key"]: stage for stage in payload["stages"]}
    assert stage_by_key["recipes"]["ok"] is True
    assert stage_by_key["recipes"]["details"] == "4 recipes"
    assert stage_by_key["dry_run_rehearsal"]["ok"] is False
    assert "Ready for lab review: True" in text
    assert "| Dry-run rehearsal | MISSING |" in text


def test_hall_workflow_status_requires_package_manifest(tmp_path):
    missing_package = tmp_path / "missing_package"
    missing_package.mkdir()

    try:
        inspect_dual_gate_lockin_hall_suite_workflow_status(missing_package)
    except FileNotFoundError as exc:
        assert "Package manifest does not exist" in str(exc)
    else:
        raise AssertionError("Expected FileNotFoundError")


def test_hall_workflow_rehearsal_runs_direct_module_api(tmp_path):
    template = write_dual_gate_lockin_hall_suite_template(
        "configs/recipes/dual_gate_lockin_four_terminal_dry_run.yaml",
        tmp_path / "suite",
        measurement_prefix="workflow_graphene",
        magnetic_field_t=1.0,
        run_output_directory=tmp_path / "raw",
    )
    _shrink_suite_recipes(
        [
            template.longitudinal_recipe,
            template.plus_hall_recipe,
            template.minus_hall_recipe,
            template.zero_hall_recipe,
        ]
    )
    package = write_dual_gate_lockin_hall_suite_acquisition_package(
        template.longitudinal_recipe,
        template.plus_hall_recipe,
        template.minus_hall_recipe,
        tmp_path / "packages",
        zero_hall_recipe=template.zero_hall_recipe,
        package_name="workflow_graphene_package",
        chunk_size=5,
    )
    manifest = json.loads(package.manifest_path.read_text(encoding="utf-8"))
    manifest["approved_next_scan"] = {"strategy": "refine_charge_neutrality_region"}
    package.manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    payload = run_dual_gate_lockin_hall_suite_approved_next_scan_rehearsal(
        package.package_dir,
        output_dir=None,
        fake_gate1_leak_resistance_ohm=1_000_000_000.0,
        fake_gate2_leak_resistance_ohm=1_000_000_000.0,
        fake_lockin_r_v=2e-6,
        fake_lockin_phase_deg=0.0,
        fake_noise_std_v=0.0,
        safety_dir="configs/safety",
        overwrite=False,
    )

    assert payload["completed"] is True
    assert set(payload["runs"]) == {"longitudinal", "plus", "minus", "zero"}
    assert (package.package_dir / "dry_run_rehearsal" / "rehearsal_summary.json").exists()
    assert (package.package_dir / "dry_run_rehearsal" / "hall_analysis" / "hall_suite_analysis_review.json").exists()
    status = inspect_dual_gate_lockin_hall_suite_workflow_status(package.manifest_path)
    stage_by_key = {stage["key"]: stage for stage in status["stages"]}
    assert stage_by_key["dry_run_rehearsal"]["ok"] is True


def test_hall_workflow_rehearsal_requires_approved_next_scan(tmp_path):
    package_dir = tmp_path / "package"
    package_dir.mkdir()
    (package_dir / "package_manifest.json").write_text(
        json.dumps({"package_name": "no_approval", "copied_recipes": {}}),
        encoding="utf-8",
    )

    try:
        run_dual_gate_lockin_hall_suite_approved_next_scan_rehearsal(
            package_dir,
            output_dir=None,
            fake_gate1_leak_resistance_ohm=1_000_000_000.0,
            fake_gate2_leak_resistance_ohm=1_000_000_000.0,
            fake_lockin_r_v=2e-6,
            fake_lockin_phase_deg=0.0,
            fake_noise_std_v=0.0,
            safety_dir="configs/safety",
            overwrite=False,
        )
    except ValueError as exc:
        assert "approved_next_scan" in str(exc)
    else:
        raise AssertionError("Expected ValueError")


def _shrink_suite_recipes(paths):
    for path in paths:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        data["gate1_sweep"]["points"] = 2
        data["gate2_sweep"]["points"] = 2
        data["gate1_sweep"]["settle_s"] = 0.0
        data["gate2_sweep"]["settle_s"] = 0.0
        data["lockin"]["read_settle_s"] = 0.0
        path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
