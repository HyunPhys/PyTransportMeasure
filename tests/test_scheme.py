import json

import pytest

from pytransport.scheme import (
    create_scheme_summary,
    finish_scheme_summary,
    format_scheme_plan,
    load_scheme_step_recipe,
    load_scheme_step_single_gate_recipe,
    load_scheme,
    resolve_scheme_steps,
)
from pytransport.recipes import load_recipe, sweep_voltages


def test_load_and_format_1k_scheme():
    scheme_path = "configs/schemes/drain_iv_1k_recipe_and_batch.yaml"
    scheme = load_scheme(scheme_path)
    steps = resolve_scheme_steps(scheme, scheme_path)
    text = format_scheme_plan(scheme, scheme_path)

    assert scheme.name == "drain_iv_1k_recipe_and_batch"
    assert len(steps) == 2
    assert steps[0].type == "drain_iv"
    assert steps[0].path.name == "drain_iv_1k_resistor.yaml"
    assert steps[1].type == "batch"
    assert steps[1].path.name == "drain_iv_1k_repeat_linear.yaml"
    assert "Scheme plan" in text
    assert "=== Step 1/2: linear_once (drain_iv) ===" in text
    assert "=== Step 2/2: repeat_stability (batch) ===" in text
    assert "Batch plan" in text


def test_load_and_format_single_gate_scheme():
    scheme_path = "configs/schemes/single_gate_dry_run_scheme.yaml"
    scheme = load_scheme(scheme_path)
    steps = resolve_scheme_steps(scheme, scheme_path)
    text = format_scheme_plan(scheme, scheme_path)

    assert scheme.name == "single_gate_dry_run_scheme"
    assert [step.type for step in steps] == ["drain_iv", "single_gate"]
    assert steps[1].path.name == "single_gate_dry_run.yaml"
    assert "=== Step 2/2: gate_transfer_map (single_gate) ===" in text
    assert "Single-Gate Sweep Plan" in text
    assert load_scheme_step_single_gate_recipe(steps[1]).measurement_name == "single_gate_dry_run"


def test_single_gate_scheme_step_rejects_overrides(tmp_path):
    path = tmp_path / "bad_single_gate_scheme.yaml"
    path.write_text(
        """
name: bad
steps:
  - type: single_gate
    recipe: ../../configs/recipes/single_gate_dry_run.yaml
    overrides:
      measurement_suffix: _bad
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        load_scheme(path)


def test_scheme_repeat_expands_steps(tmp_path):
    path = tmp_path / "repeat_scheme.yaml"
    path.write_text(
        """
name: repeated_recipe
steps:
  - type: drain_iv
    label: linear
    recipe: ../../configs/recipes/drain_iv_1k_resistor.yaml
    repeat: 2
    interval_s: 0.25
""".strip(),
        encoding="utf-8",
    )

    scheme = load_scheme(path)
    steps = resolve_scheme_steps(scheme, path)

    assert [step.label for step in steps] == ["linear_rep01", "linear_rep02"]
    assert steps[0].repeat_index == 1
    assert steps[1].repeat_count == 2
    assert steps[1].interval_s == 0.25


def test_scheme_step_requires_matching_path(tmp_path):
    path = tmp_path / "bad_scheme.yaml"
    path.write_text(
        """
name: bad
steps:
  - type: drain_iv
    batch: configs/batches/drain_iv_1k_repeat_linear.yaml
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        load_scheme(path)


def test_scheme_summary_records_completion(tmp_path):
    scheme = load_scheme("configs/schemes/drain_iv_1k_recipe_and_batch.yaml")
    scheme_dir, summary = create_scheme_summary(scheme, "scheme.yaml", dry_run=True, output_dir=tmp_path)
    summary["steps"].append({"completed": True, "label": "linear_once"})

    summary_path = finish_scheme_summary(scheme_dir, summary)
    saved = json.loads(summary_path.read_text(encoding="utf-8"))

    assert summary_path.name == "scheme_summary.json"
    assert saved["scheme_name"] == "drain_iv_1k_recipe_and_batch"
    assert saved["dry_run"] is True
    assert saved["completed"] is True


def test_scheme_overrides_modify_recipe_without_changing_base():
    scheme_path = "configs/schemes/drain_iv_1k_bias_series.yaml"
    scheme = load_scheme(scheme_path)
    steps = resolve_scheme_steps(scheme, scheme_path)
    base = load_recipe("configs/recipes/drain_iv_1k_resistor.yaml")

    low_bias = load_scheme_step_recipe(steps[0])
    nominal = load_scheme_step_recipe(steps[1])

    assert base.measurement_name == "drain_iv_1k_resistor_check"
    assert low_bias.measurement_name == "drain_iv_1k_resistor_check_low_bias"
    assert nominal.measurement_name == "drain_iv_1k_resistor_check_nominal_bias"
    assert len(sweep_voltages(low_bias.sweep)) == 11
    assert low_bias.sweep.start_v == -0.05
    assert low_bias.sweep.stop_v == 0.05
    assert "low-bias" in low_bias.experiment.tags
    assert "resistor" in low_bias.experiment.tags


def test_scheme_plan_shows_overrides():
    text = format_scheme_plan(load_scheme("configs/schemes/drain_iv_1k_bias_series.yaml"), "configs/schemes/drain_iv_1k_bias_series.yaml")

    assert "Measurement: drain_iv_1k_resistor_check_low_bias" in text
    assert "Points: 11" in text
    assert "Overrides" in text
    assert "sweep.start_v: -0.05" in text


def test_scheme_matrix_expands_rows_and_merges_overrides():
    scheme_path = "configs/schemes/drain_iv_1k_bias_matrix.yaml"
    scheme = load_scheme(scheme_path)
    steps = resolve_scheme_steps(scheme, scheme_path)
    low = load_scheme_step_recipe(steps[0])
    mid = load_scheme_step_recipe(steps[1])
    nominal = load_scheme_step_recipe(steps[2])

    assert [step.label for step in steps] == ["bias_low", "bias_mid", "bias_nominal"]
    assert [step.matrix_label for step in steps] == ["low", "mid", "nominal"]
    assert steps[0].matrix_index == 1
    assert steps[2].matrix_count == 3
    assert low.measurement_name == "drain_iv_1k_resistor_check_matrix_low"
    assert mid.measurement_name == "drain_iv_1k_resistor_check_matrix_mid"
    assert nominal.measurement_name == "drain_iv_1k_resistor_check_matrix_nominal"
    assert len(sweep_voltages(low.sweep)) == 11
    assert len(sweep_voltages(mid.sweep)) == 15
    assert len(sweep_voltages(nominal.sweep)) == 21
    assert "matrix" in low.experiment.tags
    assert "low-bias" in low.experiment.tags


def test_scheme_matrix_can_repeat_rows(tmp_path):
    path = tmp_path / "matrix_repeat.yaml"
    path.write_text(
        """
name: matrix_repeat
steps:
  - type: drain_iv
    label: bias
    recipe: ../../configs/recipes/drain_iv_1k_resistor.yaml
    repeat: 2
    matrix:
      rows:
        - label: a
          overrides:
            measurement_suffix: _a
        - label: b
          overrides:
            measurement_suffix: _b
""".strip(),
        encoding="utf-8",
    )

    steps = resolve_scheme_steps(load_scheme(path), path)

    assert [step.label for step in steps] == ["bias_a_rep01", "bias_a_rep02", "bias_b_rep01", "bias_b_rep02"]
    assert steps[1].repeat_index == 2
    assert steps[2].matrix_label == "b"
