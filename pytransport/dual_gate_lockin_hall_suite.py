"""Template helpers for a Hall-bar dual-gate lock-in measurement suite."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .dual_gate_lockin import dual_gate_lockin_point_count, format_dual_gate_lockin_plan
from .recipes import DualGateLockInRecipe, SafetyPreset, load_named_safety_preset, load_yaml


@dataclass(frozen=True)
class HallSuiteTemplateResult:
    output_dir: Path
    longitudinal_recipe: Path
    plus_hall_recipe: Path
    minus_hall_recipe: Path
    zero_hall_recipe: Path | None
    review_path: Path


def write_dual_gate_lockin_hall_suite_template(
    base_recipe_path: str | Path,
    output_dir: str | Path,
    *,
    measurement_prefix: str | None = None,
    magnetic_field_t: float,
    longitudinal_contacts: list[str] | None = None,
    hall_contacts: list[str] | None = None,
    channel_length_m: float | None = None,
    channel_width_m: float | None = None,
    include_zero_field: bool = True,
    run_output_directory: str | Path | None = None,
    safety_dir: str | Path = "configs/safety",
    overwrite: bool = False,
) -> HallSuiteTemplateResult:
    base_path = Path(base_recipe_path)
    base_data = load_yaml(base_path)
    base_recipe = DualGateLockInRecipe.model_validate(base_data)
    if magnetic_field_t <= 0:
        raise ValueError("magnetic_field_t must be positive; plus/minus recipes set the sign")

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    prefix = measurement_prefix or f"{base_recipe.measurement_name}_hall_suite"
    longitudinal_data = _recipe_variant(
        base_data,
        measurement_name=f"{prefix}_vxx",
        voltage_probe_role="longitudinal",
        magnetic_field_t=None,
        lockin_input_contacts=longitudinal_contacts,
        channel_length_m=channel_length_m,
        channel_width_m=channel_width_m,
        run_output_directory=run_output_directory,
    )
    plus_data = _recipe_variant(
        base_data,
        measurement_name=f"{prefix}_vxy_plus_b",
        voltage_probe_role="hall",
        magnetic_field_t=magnetic_field_t,
        lockin_input_contacts=hall_contacts,
        channel_length_m=None,
        channel_width_m=None,
        run_output_directory=run_output_directory,
    )
    minus_data = _recipe_variant(
        base_data,
        measurement_name=f"{prefix}_vxy_minus_b",
        voltage_probe_role="hall",
        magnetic_field_t=-magnetic_field_t,
        lockin_input_contacts=hall_contacts,
        channel_length_m=None,
        channel_width_m=None,
        run_output_directory=run_output_directory,
    )
    zero_data = (
        _recipe_variant(
            base_data,
            measurement_name=f"{prefix}_vxy_zero_b",
            voltage_probe_role="hall",
            magnetic_field_t=0.0,
            lockin_input_contacts=hall_contacts,
            channel_length_m=None,
            channel_width_m=None,
            run_output_directory=run_output_directory,
        )
        if include_zero_field
        else None
    )

    longitudinal_path = out / f"{prefix}_vxx.yaml"
    plus_path = out / f"{prefix}_vxy_plus_b.yaml"
    minus_path = out / f"{prefix}_vxy_minus_b.yaml"
    zero_path = out / f"{prefix}_vxy_zero_b.yaml" if zero_data is not None else None
    _write_recipe(longitudinal_path, longitudinal_data, overwrite=overwrite)
    _write_recipe(plus_path, plus_data, overwrite=overwrite)
    _write_recipe(minus_path, minus_data, overwrite=overwrite)
    if zero_path is not None and zero_data is not None:
        _write_recipe(zero_path, zero_data, overwrite=overwrite)

    review_path = out / f"{prefix}_review.md"
    if review_path.exists() and not overwrite:
        raise FileExistsError(f"Review file already exists: {review_path}")
    safety = load_named_safety_preset(base_recipe.safety_preset, safety_dir)
    review_path.write_text(
        format_hall_suite_review(
            base_path,
            longitudinal_path,
            plus_path,
            minus_path,
            zero_path,
            longitudinal_data,
            plus_data,
            safety,
        ),
        encoding="utf-8",
    )
    return HallSuiteTemplateResult(out, longitudinal_path, plus_path, minus_path, zero_path, review_path)


def format_hall_suite_review(
    base_recipe_path: str | Path,
    longitudinal_recipe: str | Path,
    plus_hall_recipe: str | Path,
    minus_hall_recipe: str | Path,
    zero_hall_recipe: str | Path | None,
    longitudinal_data: dict[str, Any],
    plus_data: dict[str, Any],
    safety: SafetyPreset,
) -> str:
    longitudinal_model = DualGateLockInRecipe.model_validate(longitudinal_data)
    plus_model = DualGateLockInRecipe.model_validate(plus_data)
    zero_line = f"- Zero-field Vxy: `{zero_hall_recipe}`" if zero_hall_recipe is not None else "- Zero-field Vxy: not generated"
    zero_analysis = (
        "ptm dual-gate-lockin-hall-zero-correct data\\raw\\<plus_B_run> data\\raw\\<zero_B_run> --output-dir data\\analysis\\<hall_zero_corrected_folder>"
        if zero_hall_recipe is not None
        else "# zero-field correction not generated for this suite"
    )
    return "\n".join(
        [
            "# Dual-Gate Lock-In Hall Suite Review",
            "",
            f"- Base recipe: `{base_recipe_path}`",
            f"- Longitudinal Vxx: `{longitudinal_recipe}`",
            f"- Positive-field Vxy: `{plus_hall_recipe}`",
            f"- Negative-field Vxy: `{minus_hall_recipe}`",
            zero_line,
            f"- Gate-grid points per recipe: {dual_gate_lockin_point_count(longitudinal_model)}",
            "",
            "## Hardware-Free Checks",
            "",
            "```powershell",
            f"ptm dual-gate-lockin-plan {longitudinal_recipe}",
            f"ptm dual-gate-lockin-plan {plus_hall_recipe}",
            f"ptm dual-gate-lockin-plan {minus_hall_recipe}",
            *( [f"ptm dual-gate-lockin-plan {zero_hall_recipe}"] if zero_hall_recipe is not None else [] ),
            f"ptm dual-gate-lockin-preflight {longitudinal_recipe}",
            f"ptm dual-gate-lockin-preflight {plus_hall_recipe}",
            f"ptm dual-gate-lockin-preflight {minus_hall_recipe}",
            *( [f"ptm dual-gate-lockin-preflight {zero_hall_recipe}"] if zero_hall_recipe is not None else [] ),
            "```",
            "",
            "## Hardware Run Templates",
            "",
            "Use accepted previous-run guards and point limits appropriate for the lab state.",
            "",
            "```powershell",
            f"ptm dual-gate-lockin {longitudinal_recipe} --allow-active-sweep --max-hardware-points <N> --hardware-approval-note \"<lab note>\" --accepted-previous-run data\\raw\\<accepted_run> --progress --plot --report --gate-stats",
            f"ptm dual-gate-lockin {plus_hall_recipe} --allow-active-sweep --max-hardware-points <N> --hardware-approval-note \"<lab note>\" --accepted-previous-run data\\raw\\<accepted_run> --progress --plot --report --gate-stats",
            f"ptm dual-gate-lockin {minus_hall_recipe} --allow-active-sweep --max-hardware-points <N> --hardware-approval-note \"<lab note>\" --accepted-previous-run data\\raw\\<accepted_run> --progress --plot --report --gate-stats",
            *( [f"ptm dual-gate-lockin {zero_hall_recipe} --allow-active-sweep --max-hardware-points <N> --hardware-approval-note \"<lab note>\" --accepted-previous-run data\\raw\\<accepted_run> --progress --plot --report --gate-stats"] if zero_hall_recipe is not None else [] ),
            "```",
            "",
            "## Analysis Commands",
            "",
            "```powershell",
            "ptm dual-gate-lockin-hall-antisym data\\raw\\<plus_B_run> data\\raw\\<minus_B_run> --output-dir data\\analysis\\<hall_antisym_folder>",
            zero_analysis,
            "ptm dual-gate-lockin-hall-mobility data\\analysis\\<hall_density_folder> data\\raw\\<longitudinal_Vxx_run> --output-dir data\\analysis\\<hall_mobility_folder>",
            "```",
            "",
            "## Longitudinal Plan Snapshot",
            "",
            "```text",
            format_dual_gate_lockin_plan(longitudinal_model, safety, longitudinal_recipe, preview_points=3),
            "```",
            "",
            "## Hall Plan Snapshot",
            "",
            "```text",
            format_dual_gate_lockin_plan(plus_model, safety, plus_hall_recipe, preview_points=3),
            "```",
            "",
        ]
    )


def _recipe_variant(
    base_data: dict[str, Any],
    *,
    measurement_name: str,
    voltage_probe_role: str,
    magnetic_field_t: float | None,
    lockin_input_contacts: list[str] | None,
    channel_length_m: float | None,
    channel_width_m: float | None,
    run_output_directory: str | Path | None,
) -> dict[str, Any]:
    data = dict(base_data)
    data["measurement_name"] = measurement_name
    topology = dict(data.get("topology") or {})
    topology["voltage_probe_role"] = voltage_probe_role
    if magnetic_field_t is None:
        topology.pop("magnetic_field_t", None)
    else:
        topology["magnetic_field_t"] = magnetic_field_t
    if lockin_input_contacts is not None:
        topology["lockin_input_contacts"] = list(lockin_input_contacts)
    if voltage_probe_role == "longitudinal":
        if channel_length_m is not None:
            topology["channel_length_m"] = channel_length_m
        if channel_width_m is not None:
            topology["channel_width_m"] = channel_width_m
    else:
        topology.pop("channel_length_m", None)
        topology.pop("channel_width_m", None)
    data["topology"] = topology
    if run_output_directory is not None:
        data["output"] = {**dict(data.get("output") or {}), "directory": str(run_output_directory)}
    DualGateLockInRecipe.model_validate(data)
    return data


def _write_recipe(path: Path, data: dict[str, Any], *, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise FileExistsError(f"Recipe already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, sort_keys=False)
