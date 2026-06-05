import pytest

from pytransport.plan import build_measurement_plan, format_measurement_plan


def test_build_measurement_plan_for_1k_recipe():
    plan = build_measurement_plan("configs/recipes/drain_iv_1k_resistor.yaml")
    text = format_measurement_plan(plan)

    assert plan.measurement_name == "drain_iv_1k_resistor_check"
    assert plan.sample_id == "resistor_box"
    assert plan.points == 21
    assert plan.voltage_min_v == pytest.approx(-0.1)
    assert plan.voltage_max_v == pytest.approx(0.1)
    assert plan.estimated_duration_s == pytest.approx(1.05)
    assert plan.current_compliance_a == pytest.approx(2.0e-4)
    assert plan.safety_current_limit_a == pytest.approx(5.0e-4)
    assert plan.nplc == pytest.approx(1.0)
    assert "Measurement plan" in text
    assert "- NPLC: 1" in text
    assert "Point preview" in text
    assert "... 11 points omitted ..." in text


def test_measurement_plan_preview_can_show_all_points():
    plan = build_measurement_plan("configs/recipes/drain_iv_1k_resistor.yaml", preview_count=11)
    text = format_measurement_plan(plan)

    assert len(plan.preview_points) == 21
    assert plan.preview_omitted == 0
    assert "omitted" not in text


def test_measurement_plan_rejects_invalid_preview_count():
    with pytest.raises(ValueError):
        build_measurement_plan("configs/recipes/drain_iv_1k_resistor.yaml", preview_count=0)
