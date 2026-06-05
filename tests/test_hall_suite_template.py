import yaml

from pytransport.cli import main
from pytransport.dual_gate_lockin_hall_suite import (
    audit_dual_gate_lockin_hall_suite,
    write_dual_gate_lockin_hall_suite_template,
)
from pytransport.recipes import load_dual_gate_lockin_recipe


def test_write_hall_suite_template_creates_valid_recipe_set(tmp_path):
    result = write_dual_gate_lockin_hall_suite_template(
        "configs/recipes/dual_gate_lockin_four_terminal_dry_run.yaml",
        tmp_path / "suite",
        measurement_prefix="graphene_a",
        magnetic_field_t=1.5,
        longitudinal_contacts=["Vxx+", "Vxx-"],
        hall_contacts=["Vxy+", "Vxy-"],
        channel_length_m=4e-6,
        channel_width_m=2e-6,
        run_output_directory=tmp_path / "raw",
    )

    longitudinal = load_dual_gate_lockin_recipe(result.longitudinal_recipe)
    plus = load_dual_gate_lockin_recipe(result.plus_hall_recipe)
    minus = load_dual_gate_lockin_recipe(result.minus_hall_recipe)
    zero = load_dual_gate_lockin_recipe(result.zero_hall_recipe)

    assert longitudinal.measurement_name == "graphene_a_vxx"
    assert longitudinal.topology.voltage_probe_role == "longitudinal"
    assert longitudinal.topology.lockin_input_contacts == ["Vxx+", "Vxx-"]
    assert longitudinal.topology.channel_length_m == 4e-6
    assert longitudinal.topology.channel_width_m == 2e-6
    assert longitudinal.output.directory == tmp_path / "raw"
    assert plus.measurement_name == "graphene_a_vxy_plus_b"
    assert plus.topology.voltage_probe_role == "hall"
    assert plus.topology.lockin_input_contacts == ["Vxy+", "Vxy-"]
    assert plus.topology.magnetic_field_t == 1.5
    assert plus.topology.channel_length_m is None
    assert minus.topology.magnetic_field_t == -1.5
    assert zero.topology.magnetic_field_t == 0.0
    review = result.review_path.read_text(encoding="utf-8")
    assert "dual-gate-lockin-hall-suite-check" in review
    assert "dual-gate-lockin-hall-antisym" in review
    assert "dual-gate-lockin-hall-mobility" in review

    audit = audit_dual_gate_lockin_hall_suite(
        result.longitudinal_recipe,
        result.plus_hall_recipe,
        result.minus_hall_recipe,
        zero_hall_recipe=result.zero_hall_recipe,
    )
    assert audit.compatible is True
    assert audit.point_count == 25


def test_hall_suite_template_can_skip_zero_field(tmp_path):
    result = write_dual_gate_lockin_hall_suite_template(
        "configs/recipes/dual_gate_lockin_four_terminal_dry_run.yaml",
        tmp_path / "suite",
        measurement_prefix="graphene_no_zero",
        magnetic_field_t=1.0,
        include_zero_field=False,
    )

    assert result.zero_hall_recipe is None
    files = {path.name for path in result.output_dir.iterdir()}
    assert "graphene_no_zero_vxy_zero_b.yaml" not in files
    assert "graphene_no_zero_vxy_plus_b.yaml" in files


def test_cli_dual_gate_lockin_hall_suite_template(tmp_path):
    output = tmp_path / "suite"

    code = main(
        [
            "dual-gate-lockin-hall-suite-template",
            "configs/recipes/dual_gate_lockin_four_terminal_dry_run.yaml",
            str(output),
            "--measurement-prefix",
            "cli_graphene",
            "--magnetic-field-t",
            "2.0",
            "--longitudinal-contact",
            "V1",
            "--longitudinal-contact",
            "V2",
            "--hall-contact",
            "VH1",
            "--hall-contact",
            "VH2",
        ]
    )

    assert code == 0
    assert (output / "cli_graphene_vxx.yaml").exists()
    assert (output / "cli_graphene_vxy_plus_b.yaml").exists()
    assert (output / "cli_graphene_vxy_minus_b.yaml").exists()
    assert (output / "cli_graphene_vxy_zero_b.yaml").exists()
    data = yaml.safe_load((output / "cli_graphene_vxy_plus_b.yaml").read_text(encoding="utf-8"))
    assert data["topology"]["lockin_input_contacts"] == ["VH1", "VH2"]

    code = main(
        [
            "dual-gate-lockin-hall-suite-check",
            str(output / "cli_graphene_vxx.yaml"),
            str(output / "cli_graphene_vxy_plus_b.yaml"),
            str(output / "cli_graphene_vxy_minus_b.yaml"),
            "--zero-field-recipe",
            str(output / "cli_graphene_vxy_zero_b.yaml"),
        ]
    )
    assert code == 0


def test_hall_suite_check_fails_for_mismatched_field(tmp_path):
    result = write_dual_gate_lockin_hall_suite_template(
        "configs/recipes/dual_gate_lockin_four_terminal_dry_run.yaml",
        tmp_path / "suite",
        measurement_prefix="bad_field",
        magnetic_field_t=1.0,
    )
    minus_data = yaml.safe_load(result.minus_hall_recipe.read_text(encoding="utf-8"))
    minus_data["topology"]["magnetic_field_t"] = -2.0
    result.minus_hall_recipe.write_text(yaml.safe_dump(minus_data, sort_keys=False), encoding="utf-8")

    audit = audit_dual_gate_lockin_hall_suite(
        result.longitudinal_recipe,
        result.plus_hall_recipe,
        result.minus_hall_recipe,
        zero_hall_recipe=result.zero_hall_recipe,
    )

    assert audit.compatible is False
    assert any(issue.check == "magnetic_field_t" for issue in audit.issues)
