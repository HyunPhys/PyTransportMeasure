from pathlib import Path

import pytest
from pydantic import ValidationError

from pytransport.recipes import DrainIVRecipe, load_recipe, sweep_delays, sweep_voltages


def test_load_example_recipe():
    recipe = load_recipe(Path("configs/recipes/drain_iv.yaml"))
    assert recipe.measurement_name == "drain_iv_1k_resistor_check"
    assert recipe.experiment.sample_id == "resistor_box"
    assert recipe.experiment.device_id == "1k_resistor"
    assert recipe.experiment.tags == ["smoke-test", "resistor"]
    assert recipe.safety_preset == "resistor_1k_check"
    assert recipe.instrument.terminal == "FRONT"
    assert recipe.instrument.voltage_range_v == 0.2
    assert recipe.instrument.current_range_a == 2.0e-4
    assert recipe.sweep.points == 21


def test_experiment_metadata_accepts_lab_context_fields():
    recipe = DrainIVRecipe.model_validate(
        {
            "measurement_name": "metadata_context",
            "experiment": {
                "sample_id": "sample-a",
                "device_id": "dev-1",
                "cooldown_id": "cd-2026-06",
                "contact_geometry": "2-probe wirebond",
                "contact_notes": "Au pads, left-right",
                "lab_notebook_ref": "ELN-42 p.7",
            },
            "instrument": {"address": "FAKE"},
            "sweep": {
                "start_v": -0.01,
                "stop_v": 0.01,
                "points": 3,
                "current_compliance_a": 1e-6,
            },
        }
    )

    assert recipe.experiment.cooldown_id == "cd-2026-06"
    assert recipe.experiment.contact_geometry == "2-probe wirebond"
    assert recipe.experiment.lab_notebook_ref == "ELN-42 p.7"


def test_load_phase0_recipe_templates():
    resistor = load_recipe(Path("configs/recipes/drain_iv_1k_resistor.yaml"))
    nanodevice = load_recipe(Path("configs/recipes/drain_iv_nanodevice_safe.yaml"))

    assert resistor.safety_preset == "resistor_1k_check"
    assert resistor.sweep.current_compliance_a == 2.0e-4
    assert nanodevice.safety_preset == "nano_device_safe"
    assert nanodevice.sweep.current_compliance_a == 1.0e-7


def test_forward_backward_recipe_expands_sweep():
    recipe = load_recipe(Path("configs/recipes/drain_iv_1k_forward_backward.yaml"))
    voltages = sweep_voltages(recipe.sweep)

    assert recipe.sweep.mode == "forward_backward"
    assert len(voltages) == 41
    assert voltages[0] == -0.1
    assert voltages[20] == 0.1
    assert voltages[-1] == -0.1


def test_multisegment_recipe_expands_sweep_and_delays():
    recipe = load_recipe(Path("configs/recipes/drain_iv_1k_multisegment.yaml"))
    voltages = sweep_voltages(recipe.sweep)
    delays = sweep_delays(recipe.sweep)

    assert recipe.sweep.mode == "multi_segment"
    assert len(voltages) == 21
    assert len(delays) == 21
    assert voltages[0] == -0.1
    assert voltages[10] == 0.0
    assert voltages[-1] == 0.1
    assert delays[0] == 0.05
    assert delays[-1] == 0.02


def test_recipe_rejects_voltage_range_smaller_than_sweep():
    with pytest.raises(ValidationError):
        DrainIVRecipe.model_validate(
            {
                "measurement_name": "bad_range",
                "instrument": {"address": "FAKE", "voltage_range_v": 0.05},
                "sweep": {
                    "start_v": -0.1,
                    "stop_v": 0.1,
                    "points": 3,
                    "current_compliance_a": 1e-6,
                },
            }
        )


def test_recipe_rejects_single_point():
    with pytest.raises(ValidationError):
        DrainIVRecipe.model_validate(
            {
                "measurement_name": "bad",
                "instrument": {"address": "GPIB0::24::INSTR"},
                "sweep": {
                    "start_v": 0,
                    "stop_v": 1,
                    "points": 1,
                    "current_compliance_a": 1e-9,
                },
            }
        )


def test_multisegment_requires_segments():
    with pytest.raises(ValidationError):
        DrainIVRecipe.model_validate(
            {
                "measurement_name": "bad_multisegment",
                "instrument": {"address": "GPIB0::24::INSTR"},
                "sweep": {
                    "mode": "multi_segment",
                    "current_compliance_a": 1e-9,
                },
            }
        )
