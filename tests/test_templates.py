from pathlib import Path

import pytest

from pytransport.recipes import load_recipe, sweep_voltages
from pytransport.batch import load_batch, resolve_batch_entries
from pytransport.scheme import load_scheme, resolve_scheme_steps
from pytransport.templates import write_batch_template, write_recipe_template, write_scheme_template


def test_write_linear_recipe_template(tmp_path):
    path = write_recipe_template(
        tmp_path / "linear.yaml",
        mode="linear_one_way",
        measurement_name="new_linear",
        address="GPIB0::2::INSTR",
        sample_id="sample",
        device_id="device",
    )

    recipe = load_recipe(path)

    assert recipe.measurement_name == "new_linear"
    assert recipe.experiment.sample_id == "sample"
    assert recipe.experiment.device_id == "device"
    assert len(sweep_voltages(recipe.sweep)) == 21


def test_write_multisegment_recipe_template(tmp_path):
    path = write_recipe_template(
        tmp_path / "multi.yaml",
        mode="multi_segment",
        measurement_name="new_multi",
        address="GPIB0::2::INSTR",
    )

    recipe = load_recipe(path)

    assert recipe.sweep.mode == "multi_segment"
    assert len(sweep_voltages(recipe.sweep)) == 21


def test_write_recipe_template_refuses_overwrite(tmp_path):
    path = tmp_path / "recipe.yaml"
    write_recipe_template(path, mode="linear_one_way", measurement_name="first", address="FAKE")

    with pytest.raises(FileExistsError):
        write_recipe_template(path, mode="linear_one_way", measurement_name="second", address="FAKE")


def test_write_repeat_batch_template(tmp_path):
    path = write_batch_template(
        tmp_path / "repeat.yaml",
        kind="repeat",
        name="contact_check",
        recipe="configs/recipes/drain_iv_1k_resistor.yaml",
        repeat=4,
        interval_s=0.25,
    )

    batch = load_batch(path)
    entries = resolve_batch_entries(batch, path)

    assert batch.name == "contact_check"
    assert len(entries) == 4
    assert entries[0].label == "contact_check_repeat_rep01"
    assert entries[-1].repeat_index == 4
    assert entries[-1].interval_s == 0.25


def test_write_smoke_suite_batch_template(tmp_path):
    path = write_batch_template(tmp_path / "smoke.yaml", kind="smoke_suite", name="smoke")
    batch = load_batch(path)
    entries = resolve_batch_entries(batch, path)

    assert batch.name == "smoke"
    assert [entry.label for entry in entries] == ["linear", "forward_backward", "multi_segment"]
    assert entries[0].recipe_path == Path("configs/recipes/drain_iv_1k_resistor.yaml")


def test_write_batch_template_refuses_overwrite(tmp_path):
    path = tmp_path / "batch.yaml"
    write_batch_template(path, kind="repeat", name="first")

    with pytest.raises(FileExistsError):
        write_batch_template(path, kind="repeat", name="second")


def test_write_recipe_and_batch_scheme_template(tmp_path):
    path = write_scheme_template(
        tmp_path / "scheme.yaml",
        kind="recipe_and_batch",
        name="scheme",
        recipe="../../configs/recipes/drain_iv_1k_resistor.yaml",
        batch="../../configs/batches/drain_iv_1k_repeat_linear.yaml",
    )
    scheme = load_scheme(path)
    steps = resolve_scheme_steps(scheme, path)

    assert scheme.name == "scheme"
    assert [step.type for step in steps] == ["drain_iv", "batch"]
    assert steps[0].path.name == "drain_iv_1k_resistor.yaml"


def test_write_repeat_recipe_scheme_template(tmp_path):
    path = write_scheme_template(
        tmp_path / "repeat_scheme.yaml",
        kind="repeat_recipe",
        name="contact_sequence",
        recipe="../../configs/recipes/drain_iv_1k_resistor.yaml",
        repeat=3,
        interval_s=0.1,
    )
    scheme = load_scheme(path)
    steps = resolve_scheme_steps(scheme, path)

    assert len(steps) == 3
    assert steps[0].label == "contact_sequence_linear_rep01"
    assert steps[-1].interval_s == 0.1


def test_write_scheme_template_refuses_overwrite(tmp_path):
    path = tmp_path / "scheme.yaml"
    write_scheme_template(path, kind="repeat_recipe", name="first")

    with pytest.raises(FileExistsError):
        write_scheme_template(path, kind="repeat_recipe", name="second")
