"""Recipe template generation."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml


TemplateMode = Literal["linear_one_way", "forward_backward", "multi_segment"]
BatchTemplateKind = Literal["smoke_suite", "repeat"]
SchemeTemplateKind = Literal["recipe_and_batch", "repeat_recipe"]


def recipe_template(
    mode: TemplateMode,
    measurement_name: str,
    address: str,
    sample_id: str = "",
    device_id: str = "",
    cooldown_id: str = "",
    contact_geometry: str = "",
    contact_notes: str = "",
    lab_notebook_ref: str = "",
    operator: str = "",
) -> dict:
    base = {
        "measurement_name": measurement_name,
        "safety_preset": "nano_device_safe",
        "experiment": {
            "sample_id": sample_id,
            "device_id": device_id,
            "cooldown_id": cooldown_id,
            "contact_geometry": contact_geometry,
            "contact_notes": contact_notes,
            "lab_notebook_ref": lab_notebook_ref,
            "operator": operator,
            "notes": "Fill in notes before running on a real device.",
            "tags": ["template"],
        },
        "instrument": {
            "id": "keithley_2450",
            "address": address,
            "timeout_ms": 10000,
            "terminal": "FRONT",
            "voltage_range_v": 0.2,
            "current_range_a": 1.0e-7,
            "nplc": 1.0,
        },
        "sweep": {
            "mode": mode,
            "delay_s": 0.05,
            "current_compliance_a": 1.0e-7,
        },
        "output": {"directory": "data/raw"},
    }
    if mode in {"linear_one_way", "forward_backward"}:
        base["sweep"].update({"start_v": -0.1, "stop_v": 0.1, "points": 21})
    else:
        base["sweep"]["segments"] = [
            {"start_v": -0.1, "stop_v": 0.0, "points": 11},
            {"start_v": 0.0, "stop_v": 0.1, "points": 11, "delay_s": 0.05},
        ]
    return base


def write_recipe_template(
    output_path: str | Path,
    mode: TemplateMode,
    measurement_name: str,
    address: str,
    sample_id: str = "",
    device_id: str = "",
    cooldown_id: str = "",
    contact_geometry: str = "",
    contact_notes: str = "",
    lab_notebook_ref: str = "",
    operator: str = "",
    overwrite: bool = False,
) -> Path:
    path = Path(output_path)
    if path.exists() and not overwrite:
        raise FileExistsError(f"Recipe already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    data = recipe_template(
        mode,
        measurement_name,
        address,
        sample_id,
        device_id,
        cooldown_id,
        contact_geometry,
        contact_notes,
        lab_notebook_ref,
        operator,
    )
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, sort_keys=False)
    return path


def batch_template(
    kind: BatchTemplateKind,
    name: str,
    recipe: str = "configs/recipes/drain_iv_1k_resistor.yaml",
    repeat: int = 3,
    interval_s: float = 0.5,
) -> dict:
    if kind == "smoke_suite":
        return {
            "name": name,
            "stop_on_error": True,
            "recipes": [
                {"label": "linear", "recipe": "configs/recipes/drain_iv_1k_resistor.yaml"},
                {"label": "forward_backward", "recipe": "configs/recipes/drain_iv_1k_forward_backward.yaml"},
                {"label": "multi_segment", "recipe": "configs/recipes/drain_iv_1k_multisegment.yaml"},
            ],
        }
    return {
        "name": name,
        "stop_on_error": True,
        "recipes": [
            {
                "label": f"{safe_stem(name)}_repeat",
                "recipe": recipe,
                "repeat": repeat,
                "interval_s": interval_s,
            }
        ],
    }


def write_batch_template(
    output_path: str | Path,
    kind: BatchTemplateKind,
    name: str,
    recipe: str = "configs/recipes/drain_iv_1k_resistor.yaml",
    repeat: int = 3,
    interval_s: float = 0.5,
    overwrite: bool = False,
) -> Path:
    path = Path(output_path)
    if path.exists() and not overwrite:
        raise FileExistsError(f"Batch already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    data = batch_template(kind, name, recipe, repeat, interval_s)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, sort_keys=False)
    return path


def scheme_template(
    kind: SchemeTemplateKind,
    name: str,
    recipe: str = "configs/recipes/drain_iv_1k_resistor.yaml",
    batch: str = "configs/batches/drain_iv_1k_repeat_linear.yaml",
    repeat: int = 2,
    interval_s: float = 0.5,
) -> dict:
    if kind == "repeat_recipe":
        return {
            "name": name,
            "stop_on_error": True,
            "steps": [
                {
                    "type": "drain_iv",
                    "label": f"{safe_stem(name)}_linear",
                    "recipe": recipe,
                    "repeat": repeat,
                    "interval_s": interval_s,
                }
            ],
        }
    return {
        "name": name,
        "stop_on_error": True,
        "steps": [
            {
                "type": "drain_iv",
                "label": "linear_once",
                "recipe": recipe,
            },
            {
                "type": "batch",
                "label": "repeat_stability",
                "batch": batch,
            },
        ],
    }


def write_scheme_template(
    output_path: str | Path,
    kind: SchemeTemplateKind,
    name: str,
    recipe: str = "configs/recipes/drain_iv_1k_resistor.yaml",
    batch: str = "configs/batches/drain_iv_1k_repeat_linear.yaml",
    repeat: int = 2,
    interval_s: float = 0.5,
    overwrite: bool = False,
) -> Path:
    path = Path(output_path)
    if path.exists() and not overwrite:
        raise FileExistsError(f"Scheme already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    data = scheme_template(kind, name, recipe, batch, repeat, interval_s)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, sort_keys=False)
    return path


def safe_stem(name: str) -> str:
    cleaned = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in name.strip())
    return cleaned or "batch"
