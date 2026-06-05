"""Core services used by the desktop GUI.

This module intentionally has no PySide dependency. The GUI calls these helpers
so measurement logic remains shared with the CLI and testable without opening a
window.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Literal

import yaml

from .ac_lockin import run_ac_lockin_sweep
from .feedback_bundle import create_feedback_bundle
from .doctor import format_doctor_report, run_doctor
from .inspect import read_run_metadata
from .instruments.fake import CoupledFakeDeviceState, CoupledFakeSMU, FakeLockIn, FakeSMU
from .instruments.keithley_2450 import Keithley2450
from .method_registry import handler_for_measurement_type
from .preflight import format_preflight_report, run_preflight_for_recipe
from .pulse import run_pulse_measurement
from .quality import evaluate_run_quality, quality_report_to_dict
from .recipes import load_named_safety_preset, sweep_voltages
from .run_index import append_run_index, build_index_record, filter_run_index, read_run_index
from .runner import run_drain_iv
from .scheme import SchemeRecipe, format_scheme_plan
from .single_gate import run_single_gate_sweep
from .single_gate_review import write_single_gate_stats_csv
from .visa_utils import list_resources


GuiMethod = Literal["drain_iv", "single_gate_sweep", "ac_lockin_sweep", "pulse_measurement"]
GuiProgressCallback = Callable[[Any, int], None]


@dataclass(frozen=True)
class GuiFakeSettings:
    resistance_ohm: float = 1_000_000.0
    noise_std_a: float = 0.0
    channel_resistance_ohm: float = 1_000_000.0
    gate_leak_resistance_ohm: float = 1_000_000_000.0
    gate_modulation_per_v: float = 0.0
    lockin_r_v: float = 1e-6
    lockin_phase_deg: float = 0.0
    lockin_noise_std_v: float = 0.0


@dataclass(frozen=True)
class GuiRunResult:
    metadata: dict[str, Any]
    summary_text: str
    quality_text: str
    artifact_paths: dict[str, str] = field(default_factory=dict)

    @property
    def run_dir(self) -> Path:
        return Path(str(self.metadata["run_dir"]))


@dataclass(frozen=True)
class GuiSchemaField:
    path: str
    label: str
    value: str
    kind: Literal["text", "bool", "choice", "list", "yaml"] = "text"
    choices: tuple[str, ...] = ()
    required: bool = False


@dataclass(frozen=True)
class GuiSchemaSection:
    title: str
    fields: tuple[GuiSchemaField, ...]


@dataclass(frozen=True)
class GuiSchemeStepDraft:
    type: Literal["drain_iv", "single_gate", "batch"]
    label: str
    path: str
    enabled: bool = True
    repeat: int = 1
    interval_s: float = 0.0


DRAIN_IV_FORM_FIELDS = [
    "measurement_name",
    "sample_id",
    "device_id",
    "cooldown_id",
    "contact_geometry",
    "contact_notes",
    "lab_notebook_ref",
    "operator",
    "notes",
    "tags",
    "instrument_id",
    "address",
    "timeout_ms",
    "terminal",
    "voltage_range_v",
    "current_range_a",
    "sweep_mode",
    "start_v",
    "stop_v",
    "points",
    "delay_s",
    "current_compliance_a",
    "safety_preset",
    "output_directory",
    "require_completed",
    "min_points",
    "resistance_min_ohm",
    "resistance_max_ohm",
]


def available_gui_methods() -> dict[str, str]:
    return {
        "drain_iv": "Drain I-V",
        "single_gate_sweep": "Single-gate sweep",
        "ac_lockin_sweep": "AC lock-in sweep",
        "pulse_measurement": "Pulse measurement",
    }


def default_recipe_path(measurement_type: GuiMethod) -> Path:
    paths = {
        "drain_iv": Path("configs/recipes/drain_iv_1k_resistor.yaml"),
        "single_gate_sweep": Path("configs/recipes/single_gate_dry_run.yaml"),
        "ac_lockin_sweep": Path("configs/recipes/ac_lockin_dry_run.yaml"),
        "pulse_measurement": Path("configs/recipes/pulse_dry_run.yaml"),
    }
    return paths[measurement_type]


def load_recipe_text(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8")


def default_recipe_text(measurement_type: GuiMethod) -> str:
    return load_recipe_text(default_recipe_path(measurement_type))


def validate_recipe_text(
    measurement_type: GuiMethod,
    text: str,
    safety_dir: str | Path = "configs/safety",
    preview_points: int = 5,
) -> tuple[bool, str]:
    try:
        data = yaml.safe_load(text)
        if not isinstance(data, dict):
            raise ValueError("recipe YAML must contain a mapping")
        handler = handler_for_measurement_type(measurement_type)
        recipe = recipe_from_mapping(measurement_type, data)
        safety = load_named_safety_preset(recipe.safety_preset, safety_dir)
        plan = handler.format_plan(recipe, "<editor>", safety_dir, preview_points)
        return True, "\n".join(["Validation: PASS", f"Safety preset: {safety.name}", "", plan])
    except Exception as exc:
        return False, f"Validation: FAIL\n{type(exc).__name__}: {exc}"


def default_scheme_text() -> str:
    return scheme_text_from_builder(
        "gui_scheme",
        True,
        [
            GuiSchemeStepDraft("drain_iv", "drain_reference", "../recipes/drain_iv_1k_resistor.yaml"),
            GuiSchemeStepDraft("single_gate", "gate_transfer_map", "../recipes/single_gate_dry_run.yaml"),
        ],
    )


def load_scheme_from_text(text: str) -> SchemeRecipe:
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ValueError("scheme YAML must contain a mapping")
    return SchemeRecipe.model_validate(data)


def validate_scheme_text(
    text: str,
    scheme_path: str | Path = "configs/schemes/gui_scheme.yaml",
    safety_dir: str | Path = "configs/safety",
    preview_points: int = 3,
) -> tuple[bool, str]:
    try:
        scheme = load_scheme_from_text(text)
        plan = format_scheme_plan(scheme, scheme_path, safety_dir, preview_points)
        return True, "\n".join(["Scheme validation: PASS", "", plan])
    except Exception as exc:
        return False, f"Scheme validation: FAIL\n{type(exc).__name__}: {exc}"


def format_scheme_plan_text(
    text: str,
    scheme_path: str | Path = "configs/schemes/gui_scheme.yaml",
    safety_dir: str | Path = "configs/safety",
    preview_points: int = 3,
) -> str:
    return format_scheme_plan(load_scheme_from_text(text), scheme_path, safety_dir, preview_points)


def scheme_builder_from_text(text: str) -> tuple[str, bool, tuple[GuiSchemeStepDraft, ...]]:
    scheme = load_scheme_from_text(text)
    rows: list[GuiSchemeStepDraft] = []
    for step in scheme.steps:
        path = step.batch if step.type == "batch" else step.recipe
        rows.append(
            GuiSchemeStepDraft(
                type=step.type,
                label=step.label or "",
                path="" if path is None else str(path),
                enabled=step.enabled,
                repeat=step.repeat,
                interval_s=step.interval_s,
            )
        )
    return scheme.name, scheme.stop_on_error, tuple(rows)


def scheme_text_from_builder(
    name: str,
    stop_on_error: bool,
    steps: list[GuiSchemeStepDraft] | tuple[GuiSchemeStepDraft, ...],
) -> str:
    step_data = []
    for step in steps:
        if not step.path.strip():
            raise ValueError("scheme step path is required")
        data: dict[str, Any] = {
            "type": step.type,
            "enabled": step.enabled,
            "repeat": step.repeat,
            "interval_s": step.interval_s,
        }
        if step.label.strip():
            data["label"] = step.label.strip()
        if step.type == "batch":
            data["batch"] = step.path.strip()
        else:
            data["recipe"] = step.path.strip()
        step_data.append(data)
    scheme = SchemeRecipe.model_validate(
        {
            "name": name.strip(),
            "stop_on_error": stop_on_error,
            "steps": step_data,
        }
    )
    return yaml.safe_dump(scheme.model_dump(mode="json", exclude_none=True), sort_keys=False)


def load_recipe_from_text(measurement_type: GuiMethod, text: str) -> Any:
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ValueError("recipe YAML must contain a mapping")
    return recipe_from_mapping(measurement_type, data)


def save_recipe_text(
    measurement_type: GuiMethod,
    text: str,
    path: str | Path,
    safety_dir: str | Path = "configs/safety",
) -> Path:
    ok, message = validate_recipe_text(measurement_type, text, safety_dir)
    if not ok:
        raise ValueError(message)
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text, encoding="utf-8")
    return output


def schema_form_from_text(measurement_type: GuiMethod, text: str) -> tuple[GuiSchemaSection, ...]:
    recipe = load_recipe_from_text(measurement_type, text)
    data = recipe.model_dump(mode="json", exclude_none=False)
    schema = type(recipe).model_json_schema()
    sections: list[GuiSchemaSection] = []
    general_fields: list[GuiSchemaField] = []
    root_required = set(schema.get("required") or [])
    properties = schema.get("properties") or {}

    for key, value in data.items():
        node = _resolve_schema_node(schema, properties.get(key) or {})
        if isinstance(value, dict):
            fields = _schema_fields_for_mapping(
                schema,
                node,
                value,
                parent_path=key,
                parent_label="",
            )
            if fields:
                sections.append(GuiSchemaSection(_overview_title(key), tuple(fields)))
        else:
            general_fields.append(_schema_field(schema, node, key, value, required=key in root_required))
    if general_fields:
        sections.insert(0, GuiSchemaSection("General", tuple(general_fields)))
    return tuple(sections)


def schema_form_text_from_values(
    measurement_type: GuiMethod,
    text: str,
    values: dict[str, str],
) -> str:
    recipe = load_recipe_from_text(measurement_type, text)
    data = recipe.model_dump(mode="json", exclude_none=False)
    schema = type(recipe).model_json_schema()
    properties = schema.get("properties") or {}
    for path, raw_value in values.items():
        path_parts = path.split(".")
        node = _schema_node_for_path(schema, properties, path_parts)
        _set_nested_value(data, path_parts, _parse_schema_value(schema, node, raw_value))
    validated = recipe_from_mapping(measurement_type, data)
    return yaml.safe_dump(validated.model_dump(mode="json", exclude_none=True), sort_keys=False)


def _schema_fields_for_mapping(
    root_schema: dict[str, Any],
    schema_node: dict[str, Any],
    values: dict[str, Any],
    parent_path: str,
    parent_label: str,
) -> list[GuiSchemaField]:
    fields: list[GuiSchemaField] = []
    schema_node = _resolve_schema_node(root_schema, schema_node)
    required = set(schema_node.get("required") or [])
    properties = schema_node.get("properties") or {}
    for key, value in values.items():
        path = f"{parent_path}.{key}"
        label = _overview_label(key) if not parent_label else f"{parent_label} / {_overview_label(key)}"
        node = _resolve_schema_node(root_schema, properties.get(key) or {})
        if isinstance(value, dict) and _schema_node_type(root_schema, node) == "object":
            fields.extend(_schema_fields_for_mapping(root_schema, node, value, path, label))
        else:
            fields.append(_schema_field(root_schema, node, path, value, required=key in required, label=label))
    return fields


def _schema_field(
    root_schema: dict[str, Any],
    schema_node: dict[str, Any],
    path: str,
    value: Any,
    required: bool,
    label: str | None = None,
) -> GuiSchemaField:
    schema_node = _resolve_schema_node(root_schema, schema_node)
    choices = tuple(str(choice) for choice in schema_node.get("enum") or [])
    if choices and not required:
        choices = ("",) + choices
    if choices:
        kind: Literal["text", "bool", "choice", "list", "yaml"] = "choice"
    elif _schema_node_type(root_schema, schema_node) == "boolean" or isinstance(value, bool):
        kind = "bool"
    elif isinstance(value, list) and all(not isinstance(item, dict) for item in value):
        kind = "list"
    elif isinstance(value, (dict, list)):
        kind = "yaml"
    else:
        kind = "text"
    return GuiSchemaField(
        path=path,
        label=label or _overview_label(path),
        value=_schema_form_value(value, kind),
        kind=kind,
        choices=choices,
        required=required,
    )


def _schema_form_value(value: Any, kind: str) -> str:
    if value is None:
        return ""
    if kind == "bool":
        return str(bool(value)).lower()
    if kind == "list" and isinstance(value, list):
        return ", ".join(str(item) for item in value)
    if kind == "yaml":
        return yaml.safe_dump(value, sort_keys=False).strip()
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)


def _schema_node_for_path(root_schema: dict[str, Any], properties: dict[str, Any], path_parts: list[str]) -> dict[str, Any]:
    node = _resolve_schema_node(root_schema, properties.get(path_parts[0]) or {})
    for part in path_parts[1:]:
        node = _resolve_schema_node(root_schema, node)
        node = _resolve_schema_node(root_schema, (node.get("properties") or {}).get(part) or {})
    return node


def _parse_schema_value(root_schema: dict[str, Any], schema_node: dict[str, Any], raw_value: str) -> Any:
    text = raw_value.strip()
    schema_node = _resolve_schema_node(root_schema, schema_node)
    node_type = _schema_node_type(root_schema, schema_node)
    if text == "" and schema_node.get("enum"):
        return None
    if schema_node.get("enum"):
        return text
    if node_type == "array":
        if text == "":
            return []
        item_node = _resolve_schema_node(root_schema, schema_node.get("items") or {})
        if _schema_node_type(root_schema, item_node) == "object":
            parsed = yaml.safe_load(text) if text else []
            return parsed or []
        return [item.strip() for item in text.split(",") if item.strip()]
    if node_type == "object":
        if text == "":
            return {}
        parsed = yaml.safe_load(text) if text else {}
        return parsed or {}
    if text == "":
        return None
    if node_type == "boolean":
        return _bool_from_text(text)
    if node_type == "integer":
        return int(text)
    if node_type == "number":
        return float(text)
    return text


def _set_nested_value(data: dict[str, Any], path_parts: list[str], value: Any) -> None:
    cursor = data
    for part in path_parts[:-1]:
        next_value = cursor.get(part)
        if not isinstance(next_value, dict):
            next_value = {}
            cursor[part] = next_value
        cursor = next_value
    cursor[path_parts[-1]] = value


def _resolve_schema_node(root_schema: dict[str, Any], node: dict[str, Any]) -> dict[str, Any]:
    if "$ref" in node:
        ref_name = str(node["$ref"]).split("/")[-1]
        return _resolve_schema_node(root_schema, (root_schema.get("$defs") or {}).get(ref_name) or {})
    for key in ["anyOf", "oneOf"]:
        options = node.get(key)
        if isinstance(options, list):
            for option in options:
                resolved = _resolve_schema_node(root_schema, option)
                if resolved.get("type") != "null":
                    merged = dict(resolved)
                    if "default" in node and "default" not in merged:
                        merged["default"] = node["default"]
                    return merged
    return node


def _schema_node_type(root_schema: dict[str, Any], node: dict[str, Any]) -> str | None:
    return _resolve_schema_node(root_schema, node).get("type")


def drain_iv_form_from_text(text: str) -> dict[str, str]:
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ValueError("recipe YAML must contain a mapping")
    recipe = recipe_from_mapping("drain_iv", data)
    checks = recipe.checks
    resistance_check = checks.fitted_resistance_ohm if checks else None
    return {
        "measurement_name": recipe.measurement_name,
        "sample_id": recipe.experiment.sample_id or "",
        "device_id": recipe.experiment.device_id or "",
        "cooldown_id": recipe.experiment.cooldown_id or "",
        "contact_geometry": recipe.experiment.contact_geometry or "",
        "contact_notes": recipe.experiment.contact_notes or "",
        "lab_notebook_ref": recipe.experiment.lab_notebook_ref or "",
        "operator": recipe.experiment.operator or "",
        "notes": recipe.experiment.notes or "",
        "tags": ", ".join(recipe.experiment.tags),
        "instrument_id": recipe.instrument.id,
        "address": recipe.instrument.address,
        "timeout_ms": str(recipe.instrument.timeout_ms),
        "terminal": recipe.instrument.terminal or "",
        "voltage_range_v": _optional_float_text(recipe.instrument.voltage_range_v),
        "current_range_a": _optional_float_text(recipe.instrument.current_range_a),
        "sweep_mode": recipe.sweep.mode,
        "start_v": _optional_float_text(recipe.sweep.start_v),
        "stop_v": _optional_float_text(recipe.sweep.stop_v),
        "points": "" if recipe.sweep.points is None else str(recipe.sweep.points),
        "delay_s": str(recipe.sweep.delay_s),
        "current_compliance_a": str(recipe.sweep.current_compliance_a),
        "safety_preset": recipe.safety_preset,
        "output_directory": str(recipe.output.directory),
        "require_completed": str(checks.require_completed if checks else True).lower(),
        "min_points": "" if checks is None or checks.min_points is None else str(checks.min_points),
        "resistance_min_ohm": "" if resistance_check is None else _optional_float_text(resistance_check.min_ohm),
        "resistance_max_ohm": "" if resistance_check is None else _optional_float_text(resistance_check.max_ohm),
    }


def drain_iv_text_from_form(values: dict[str, str]) -> str:
    sweep_mode = (values.get("sweep_mode") or "linear_one_way").strip()
    recipe_data: dict[str, Any] = {
        "measurement_name": _required_text(values, "measurement_name"),
        "safety_preset": _required_text(values, "safety_preset"),
        "experiment": {
            "sample_id": _optional_text(values.get("sample_id")),
            "device_id": _optional_text(values.get("device_id")),
            "cooldown_id": _optional_text(values.get("cooldown_id")),
            "contact_geometry": _optional_text(values.get("contact_geometry")),
            "contact_notes": _optional_text(values.get("contact_notes")),
            "lab_notebook_ref": _optional_text(values.get("lab_notebook_ref")),
            "operator": _optional_text(values.get("operator")),
            "notes": _optional_text(values.get("notes")),
            "tags": _split_tags(values.get("tags", "")),
        },
        "instrument": {
            "id": values.get("instrument_id", "keithley_2450").strip() or "keithley_2450",
            "address": _required_text(values, "address"),
            "timeout_ms": _required_int(values, "timeout_ms"),
            "terminal": _optional_text(values.get("terminal")),
            "voltage_range_v": _optional_float(values.get("voltage_range_v")),
            "current_range_a": _optional_float(values.get("current_range_a")),
        },
        "sweep": {
            "mode": sweep_mode,
            "start_v": _required_float(values, "start_v"),
            "stop_v": _required_float(values, "stop_v"),
            "points": _required_int(values, "points"),
            "delay_s": _required_float(values, "delay_s"),
            "current_compliance_a": _required_float(values, "current_compliance_a"),
        },
        "output": {
            "directory": _required_text(values, "output_directory"),
        },
    }
    checks = _checks_from_form(values)
    if checks:
        recipe_data["checks"] = checks
    recipe = recipe_from_mapping("drain_iv", recipe_data)
    return yaml.safe_dump(recipe.model_dump(mode="json", exclude_none=True), sort_keys=False)


def _checks_from_form(values: dict[str, str]) -> dict[str, Any] | None:
    checks: dict[str, Any] = {"require_completed": _bool_from_text(values.get("require_completed", "true"))}
    min_points = _optional_int(values.get("min_points"))
    if min_points is not None:
        checks["min_points"] = min_points
    resistance_min = _optional_float(values.get("resistance_min_ohm"))
    resistance_max = _optional_float(values.get("resistance_max_ohm"))
    if resistance_min is not None or resistance_max is not None:
        checks["fitted_resistance_ohm"] = {
            "min_ohm": resistance_min,
            "max_ohm": resistance_max,
        }
    return checks


def _required_text(values: dict[str, str], key: str) -> str:
    value = values.get(key, "").strip()
    if not value:
        raise ValueError(f"{key} is required")
    return value


def _optional_text(value: str | None) -> str | None:
    value = (value or "").strip()
    return value or None


def _required_float(values: dict[str, str], key: str) -> float:
    value = _optional_float(values.get(key))
    if value is None:
        raise ValueError(f"{key} is required")
    return value


def _optional_float(value: str | None) -> float | None:
    text = (value or "").strip()
    return None if not text else float(text)


def _optional_float_text(value: float | None) -> str:
    return "" if value is None else f"{value:g}"


def _required_int(values: dict[str, str], key: str) -> int:
    value = _optional_int(values.get(key))
    if value is None:
        raise ValueError(f"{key} is required")
    return value


def _optional_int(value: str | None) -> int | None:
    text = (value or "").strip()
    return None if not text else int(text)


def _bool_from_text(value: str) -> bool:
    text = value.strip().lower()
    if text in {"true", "1", "yes", "y"}:
        return True
    if text in {"false", "0", "no", "n"}:
        return False
    raise ValueError("require_completed must be true or false")


def _split_tags(value: str) -> list[str]:
    return [tag.strip() for tag in value.split(",") if tag.strip()]


def recipe_from_mapping(measurement_type: GuiMethod, data: dict[str, Any]) -> Any:
    handler = handler_for_measurement_type(measurement_type)
    # Reuse each method loader's underlying Pydantic model without writing a
    # temporary file.
    model = type(handler.load_recipe(default_recipe_path(measurement_type)))
    return model.model_validate(data)


def format_gui_plan_text(
    measurement_type: GuiMethod,
    text: str,
    safety_dir: str | Path = "configs/safety",
    preview_points: int = 5,
) -> str:
    handler = handler_for_measurement_type(measurement_type)
    recipe = load_recipe_from_text(measurement_type, text)
    load_named_safety_preset(recipe.safety_preset, safety_dir)
    return handler.format_plan(recipe, "<editor>", safety_dir, preview_points)


def format_recipe_overview_text(measurement_type: GuiMethod, text: str) -> str:
    handler = handler_for_measurement_type(measurement_type)
    recipe = load_recipe_from_text(measurement_type, text)
    data = recipe.model_dump(mode="json", exclude_none=True)
    lines = [
        "Recipe Overview",
        "",
        f"Method: {handler.display_name} ({handler.measurement_type})",
        f"Measurement: {data.get('measurement_name') or 'n/a'}",
        f"Safety preset: {data.get('safety_preset') or 'n/a'}",
    ]

    _append_overview_block(
        lines,
        "Experiment",
        data.get("experiment") or {},
        [
            "sample_id",
            "device_id",
            "cooldown_id",
            "contact_geometry",
            "contact_notes",
            "lab_notebook_ref",
            "operator",
            "tags",
            "notes",
        ],
    )
    for block_name in [
        "instrument",
        "drain_instrument",
        "gate_instrument",
        "source_instrument",
        "lockin",
    ]:
        _append_overview_block(lines, _overview_title(block_name), data.get(block_name) or {})
    for block_name in [
        "sweep",
        "drain_sweep",
        "gate_sweep",
        "bias_sweep",
        "pulse",
        "pulse_limits",
        "checks",
        "output",
    ]:
        _append_overview_block(lines, _overview_title(block_name), data.get(block_name) or {})
    return "\n".join(lines)


def _append_overview_block(
    lines: list[str],
    title: str,
    values: dict[str, Any],
    ordered_keys: list[str] | None = None,
) -> None:
    if not values:
        return
    keys = ordered_keys or list(values)
    rows = [(key, values.get(key)) for key in keys if _overview_has_value(values.get(key))]
    extra_keys = [key for key in values if key not in keys and _overview_has_value(values.get(key))]
    rows.extend((key, values.get(key)) for key in extra_keys)
    if not rows:
        return
    lines.extend(["", title])
    for key, value in rows:
        lines.append(f"- {_overview_label(key)}: {_overview_value(value)}")


def _overview_has_value(value: Any) -> bool:
    return value is not None and value != "" and value != [] and value != {}


def _overview_title(name: str) -> str:
    return name.replace("_", " ").title()


def _overview_label(name: str) -> str:
    return name.replace("_", " ")


def _overview_value(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:g}"
    if isinstance(value, list):
        return ", ".join(_overview_value(item) for item in value) or "n/a"
    if isinstance(value, dict):
        parts = [f"{_overview_label(str(key))}={_overview_value(item)}" for key, item in value.items() if _overview_has_value(item)]
        return ", ".join(parts) or "n/a"
    return str(value)


def format_gui_plan(
    measurement_type: GuiMethod,
    recipe_path: str | Path,
    safety_dir: str | Path = "configs/safety",
    preview_points: int = 5,
) -> str:
    handler = handler_for_measurement_type(measurement_type)
    recipe = handler.load_recipe(recipe_path)
    return handler.format_plan(recipe, recipe_path, safety_dir, preview_points)


def run_gui_dry_run_text(
    measurement_type: GuiMethod,
    text: str,
    safety_dir: str | Path = "configs/safety",
    fake: GuiFakeSettings | None = None,
    index_path: str | Path = "data/run_index.jsonl",
    draft_dir: str | Path = "data/gui_drafts",
    create_plot: bool = True,
    create_report: bool = True,
    progress_callback: GuiProgressCallback | None = None,
    stop_requested=None,
) -> GuiRunResult:
    recipe = load_recipe_from_text(measurement_type, text)
    draft_path = write_gui_draft_recipe(measurement_type, recipe.measurement_name, text, draft_dir)
    return run_gui_dry_run(
        measurement_type,
        draft_path,
        safety_dir=safety_dir,
        fake=fake,
        index_path=index_path,
        create_plot=create_plot,
        create_report=create_report,
        progress_callback=progress_callback,
        stop_requested=stop_requested,
    )


def run_gui_preflight_text(
    measurement_type: GuiMethod,
    text: str,
    safety_dir: str | Path = "configs/safety",
    resource_lister=None,
    probe_factory=None,
    draft_dir: str | Path = "data/gui_drafts",
) -> str:
    if measurement_type != "drain_iv":
        raise ValueError("GUI preflight currently supports Drain I-V recipes only")
    recipe = load_recipe_from_text(measurement_type, text)
    draft_path = write_gui_draft_recipe(measurement_type, recipe.measurement_name, text, draft_dir)
    kwargs = {}
    if resource_lister is not None:
        kwargs["resource_lister"] = resource_lister
    if probe_factory is not None:
        kwargs["probe_factory"] = probe_factory
    report = run_preflight_for_recipe(recipe, draft_path, safety_dir=safety_dir, **kwargs)
    return format_preflight_report(report)


def run_gui_doctor_text(
    measurement_type: GuiMethod,
    text: str,
    timeout_ms: int = 10000,
    resource_lister=None,
    probe_factory=None,
) -> str:
    address = None
    if measurement_type == "drain_iv":
        recipe = load_recipe_from_text(measurement_type, text)
        address = recipe.instrument.address
        timeout_ms = recipe.instrument.timeout_ms
    kwargs = {}
    if resource_lister is not None:
        kwargs["resource_lister"] = resource_lister
    if probe_factory is not None:
        kwargs["probe_factory"] = probe_factory
    report = run_doctor(address=address, timeout_ms=timeout_ms, **kwargs)
    return format_doctor_report(report)


def refresh_gui_instruments(resource_lister=None) -> tuple[tuple[str, ...], str]:
    lister = resource_lister or list_resources
    try:
        resources = tuple(lister())
        return resources, format_gui_resource_list(resources)
    except Exception as exc:
        return (), f"Instrument refresh failed\n\n{type(exc).__name__}: {exc}"


def format_gui_resource_list(resources: tuple[str, ...]) -> str:
    lines = ["Detected VISA resources", ""]
    if resources:
        lines.extend(f"- {resource}" for resource in resources)
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "Use Test Selected Address to run a communication probe on one resource.",
            "Use Full Doctor to include Python, PyVISA, resource, and Keithley probe details.",
        ]
    )
    return "\n".join(lines)


def run_gui_communication_test(
    address: str,
    timeout_ms: int = 10000,
    resource_lister=None,
    probe_factory=None,
) -> str:
    address = address.strip()
    if not address:
        raise ValueError("Select or enter a VISA address before testing communication")
    kwargs = {}
    if resource_lister is not None:
        kwargs["resource_lister"] = resource_lister
    if probe_factory is not None:
        kwargs["probe_factory"] = probe_factory
    report = run_doctor(address=address, timeout_ms=timeout_ms, **kwargs)
    return format_doctor_report(report)


def run_gui_hardware_text(
    measurement_type: GuiMethod,
    text: str,
    safety_dir: str | Path = "configs/safety",
    index_path: str | Path = "data/run_index.jsonl",
    draft_dir: str | Path = "data/gui_drafts",
    create_plot: bool = True,
    create_report: bool = True,
    resource_lister=None,
    probe_factory=None,
    smu_factory=None,
    progress_callback: GuiProgressCallback | None = None,
    stop_requested=None,
) -> GuiRunResult:
    if measurement_type != "drain_iv":
        raise ValueError("GUI hardware runs currently support Drain I-V recipes only")
    recipe = load_recipe_from_text(measurement_type, text)
    draft_path = write_gui_draft_recipe(measurement_type, recipe.measurement_name, text, draft_dir)
    preflight_kwargs = {}
    if resource_lister is not None:
        preflight_kwargs["resource_lister"] = resource_lister
    if probe_factory is not None:
        preflight_kwargs["probe_factory"] = probe_factory
    preflight = run_preflight_for_recipe(recipe, draft_path, safety_dir=safety_dir, **preflight_kwargs)
    if not preflight.ok:
        raise RuntimeError("Hardware run blocked because preflight did not pass.\n\n" + format_preflight_report(preflight))
    safety = load_named_safety_preset(recipe.safety_preset, safety_dir)
    factory = smu_factory or (lambda address, timeout_ms: Keithley2450(address, timeout_ms))
    smu = factory(recipe.instrument.address, recipe.instrument.timeout_ms)
    metadata = run_drain_iv(
        recipe,
        safety,
        smu,
        recipe_path=draft_path,
        progress_callback=progress_callback,
        stop_requested=stop_requested,
    )
    metadata.setdefault("measurement_type", measurement_type)
    return finalize_gui_run_result(
        measurement_type,
        metadata,
        index_path=index_path,
        create_plot=create_plot,
        create_report=create_report,
    )


def format_hardware_confirmation_text(measurement_type: GuiMethod, text: str) -> str:
    if measurement_type != "drain_iv":
        raise ValueError("GUI hardware runs currently support Drain I-V recipes only")
    recipe = load_recipe_from_text(measurement_type, text)
    voltages = sweep_voltages(recipe.sweep)
    return "\n".join(
        [
            "This will turn Keithley output ON and run a hardware Drain I-V sweep.",
            "",
            f"Measurement: {recipe.measurement_name}",
            f"Address: {recipe.instrument.address}",
            f"Terminal: {recipe.instrument.terminal or 'unchanged'}",
            f"Sweep: {min(voltages):g} V to {max(voltages):g} V",
            f"Points: {len(voltages)}",
            f"Compliance: {recipe.sweep.current_compliance_a:g} A",
            f"Safety preset: {recipe.safety_preset}",
            "",
            "Preflight will run again immediately before output is enabled.",
        ]
    )


def run_gui_dry_run(
    measurement_type: GuiMethod,
    recipe_path: str | Path,
    safety_dir: str | Path = "configs/safety",
    fake: GuiFakeSettings | None = None,
    index_path: str | Path = "data/run_index.jsonl",
    create_plot: bool = True,
    create_report: bool = True,
    progress_callback: GuiProgressCallback | None = None,
    stop_requested=None,
) -> GuiRunResult:
    fake_settings = fake or GuiFakeSettings()
    handler = handler_for_measurement_type(measurement_type)
    recipe = handler.load_recipe(recipe_path)
    safety = load_named_safety_preset(recipe.safety_preset, safety_dir)

    if measurement_type == "drain_iv":
        metadata = run_drain_iv(
            recipe,
            safety,
            FakeSMU(fake_settings.resistance_ohm, fake_settings.noise_std_a),
            recipe_path=recipe_path,
            progress_callback=progress_callback,
            stop_requested=stop_requested,
        )
    elif measurement_type == "single_gate_sweep":
        state = CoupledFakeDeviceState(
            channel_resistance_ohm=fake_settings.channel_resistance_ohm,
            gate_leak_resistance_ohm=fake_settings.gate_leak_resistance_ohm,
            gate_modulation_per_v=fake_settings.gate_modulation_per_v,
            noise_std_a=fake_settings.noise_std_a,
        )
        metadata = run_single_gate_sweep(
            recipe,
            safety,
            CoupledFakeSMU("drain", state),
            CoupledFakeSMU("gate", state),
            recipe_path=recipe_path,
            progress_callback=progress_callback,
        )
    elif measurement_type == "ac_lockin_sweep":
        metadata = run_ac_lockin_sweep(
            recipe,
            safety,
            FakeSMU(fake_settings.resistance_ohm, fake_settings.noise_std_a),
            FakeLockIn(
                signal_r_v=fake_settings.lockin_r_v,
                phase_deg=fake_settings.lockin_phase_deg,
                noise_std_v=fake_settings.lockin_noise_std_v,
            ),
            recipe_path=recipe_path,
            progress_callback=progress_callback,
        )
    elif measurement_type == "pulse_measurement":
        metadata = run_pulse_measurement(
            recipe,
            safety,
            FakeSMU(fake_settings.resistance_ohm, fake_settings.noise_std_a),
            recipe_path=recipe_path,
            sleep=False,
            progress_callback=progress_callback,
        )
    else:
        raise ValueError(f"Unsupported GUI method: {measurement_type}")

    metadata.setdefault("measurement_type", measurement_type)
    return finalize_gui_run_result(
        measurement_type,
        metadata,
        index_path=index_path,
        create_plot=create_plot,
        create_report=create_report,
    )


def finalize_gui_run_result(
    measurement_type: GuiMethod,
    metadata: dict[str, Any],
    index_path: str | Path = "data/run_index.jsonl",
    create_plot: bool = True,
    create_report: bool = True,
) -> GuiRunResult:
    handler = handler_for_measurement_type(measurement_type)
    run_dir = Path(metadata["run_dir"])
    artifact_paths: dict[str, str] = {}
    if create_plot and metadata["points_written"] > 0:
        plot_path = handler.write_plot(run_dir, None)
        artifact_paths["plot_path"] = str(plot_path)
        metadata[path_metadata_key(handler.plot_filename)] = str(plot_path)
    if measurement_type == "single_gate_sweep" and metadata["points_written"] > 0:
        stats_path = write_single_gate_stats_csv(run_dir)
        artifact_paths["single_gate_stats_path"] = str(stats_path)
        metadata["single_gate_stats_path"] = str(stats_path)
    if create_report and metadata["points_written"] > 0:
        report_path = handler.write_report(run_dir, None)
        artifact_paths["report_path"] = str(report_path)
        metadata[path_metadata_key(handler.report_filename)] = str(report_path)

    quality_report = evaluate_run_quality(run_dir)
    metadata["quality"] = quality_report_to_dict(quality_report)
    write_metadata(metadata)
    append_run_index(metadata, index_path)
    summary_text = handler.format_summary(handler.summarize(run_dir)) if metadata["points_written"] > 0 else ""
    return GuiRunResult(
        metadata=metadata,
        summary_text=summary_text,
        quality_text=format_gui_quality(quality_report),
        artifact_paths=artifact_paths,
    )


def write_gui_draft_recipe(
    measurement_type: GuiMethod,
    measurement_name: str,
    text: str,
    draft_dir: str | Path = "data/gui_drafts",
) -> Path:
    directory = Path(draft_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{safe_filename(measurement_type)}_{safe_filename(measurement_name)}.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def safe_filename(value: str) -> str:
    cleaned = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in value.strip())
    cleaned = cleaned.strip("_")
    return cleaned or "recipe"


def list_gui_runs(
    index_path: str | Path = "data/run_index.jsonl",
    limit: int = 100,
    source_dir: str | Path | None = None,
    sample_id: str | None = None,
    device_id: str | None = None,
    cooldown_id: str | None = None,
    tag: str | None = None,
    measurement_type: str | None = None,
    completed: bool | None = None,
    failed: bool = False,
    interrupted: bool | None = None,
) -> list[dict[str, Any]]:
    records = list_gui_runs_from_directory(source_dir) if source_dir else read_run_index(index_path)
    records = filter_run_index(
        records,
        sample_id=blank_to_none(sample_id),
        device_id=blank_to_none(device_id),
        cooldown_id=blank_to_none(cooldown_id),
        tag=blank_to_none(tag),
        measurement_type=blank_to_none(measurement_type),
        completed=completed,
        failed=failed,
        interrupted=interrupted,
    )
    return list(reversed(records[-limit:]))


def list_gui_runs_from_directory(source_dir: str | Path | None) -> list[dict[str, Any]]:
    if source_dir is None:
        return []
    root = Path(source_dir).expanduser()
    if not root.exists():
        return []
    records: list[dict[str, Any]] = []
    metadata_paths = []
    if (root / "metadata.json").exists():
        metadata_paths.append(root / "metadata.json")
    metadata_paths.extend(sorted(root.glob("*/metadata.json")))
    for metadata_path in metadata_paths:
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(metadata, dict):
            records.append(build_index_record(metadata))
    records.sort(key=lambda record: record.get("started_at") or "")
    return records


def blank_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    return text or None


def load_gui_saved_run(run_dir: str | Path) -> GuiRunResult:
    metadata = read_run_metadata(run_dir)
    handler = handler_for_measurement_type(str(metadata.get("measurement_type") or "drain_iv"))
    summary_text = ""
    if Path(run_dir, "points.csv").exists():
        summary_text = handler.format_summary(handler.summarize(run_dir))
    quality = metadata.get("quality") or {}
    quality_text = f"Quality: {quality.get('status') or 'n/a'}"
    for result in quality.get("results") or []:
        mark = "PASS" if result.get("passed") else "FAIL"
        quality_text += f"\n- {result.get('name')}: {mark} ({result.get('message')})"
    return GuiRunResult(
        metadata=metadata,
        summary_text=summary_text,
        quality_text=quality_text,
        artifact_paths=artifact_paths_from_metadata(metadata),
    )


def create_gui_feedback_bundle(
    run_dir: str | Path,
    output_dir: str | Path = "data/feedback",
    extra_files: list[str | Path] | None = None,
) -> Path:
    return create_feedback_bundle(run_dir, output_dir=output_dir, extra_files=extra_files).zip_path


def artifact_paths_from_metadata(metadata: dict[str, Any]) -> dict[str, str]:
    paths = {}
    for key in [
        "plot_path",
        "report_path",
        "single_gate_heatmap_path",
        "single_gate_report_path",
        "single_gate_stats_path",
        "ac_lockin_plot_path",
        "ac_lockin_report_path",
        "pulse_plot_path",
        "pulse_report_path",
    ]:
        value = metadata.get(key)
        if value:
            paths[key] = str(value)
    return paths


def primary_plot_path(metadata: dict[str, Any]) -> Path | None:
    return primary_existing_path(
        metadata,
        ["plot_path", "single_gate_heatmap_path", "ac_lockin_plot_path", "pulse_plot_path"],
    )


def primary_report_path(metadata: dict[str, Any]) -> Path | None:
    return primary_existing_path(
        metadata,
        ["report_path", "single_gate_report_path", "ac_lockin_report_path", "pulse_report_path"],
    )


def primary_existing_path(metadata: dict[str, Any], keys: list[str]) -> Path | None:
    for key in keys:
        value = metadata.get(key)
        if value and Path(value).exists():
            return Path(value)
    return None


def path_metadata_key(filename: str) -> str:
    return {
        "iv_plot.svg": "plot_path",
        "report.md": "report_path",
        "single_gate_heatmap.svg": "single_gate_heatmap_path",
        "single_gate_report.md": "single_gate_report_path",
        "ac_lockin_plot.svg": "ac_lockin_plot_path",
        "ac_lockin_report.md": "ac_lockin_report_path",
        "pulse_plot.svg": "pulse_plot_path",
        "pulse_report.md": "pulse_report_path",
    }.get(filename, f"{Path(filename).stem}_path")


def write_metadata(metadata: dict[str, Any]) -> None:
    metadata_path = Path(str(metadata["metadata_path"]))
    with metadata_path.open("w", encoding="utf-8") as handle:
        json.dump(metadata, handle, indent=2, sort_keys=True, default=str)


def format_gui_quality(report) -> str:
    lines = [f"Quality: {report.status}"]
    for result in report.results:
        mark = "PASS" if result.passed else "FAIL"
        lines.append(f"- {result.name}: {mark} ({result.message})")
    return "\n".join(lines)


def format_gui_progress(point: Any, total_points: int) -> str:
    index = int(getattr(point, "index", 0)) + 1
    elapsed = float(getattr(point, "elapsed_s", 0.0))
    if hasattr(point, "voltage_v"):
        return (
            f"{index}/{total_points} | V={point.voltage_v:.6g} V | "
            f"I={point.current_a:.6g} A | R={_format_optional(point.resistance_ohm, ' ohm')} | "
            f"t={elapsed:.3f} s"
        )
    if hasattr(point, "gate_voltage_v"):
        return (
            f"{index}/{total_points} | Vg={point.gate_voltage_v:.6g} V | "
            f"Vd={point.drain_voltage_v:.6g} V | Id={point.drain_current_a:.6g} A | "
            f"Ig={point.gate_current_a:.6g} A | t={elapsed:.3f} s"
        )
    if hasattr(point, "bias_voltage_v"):
        return (
            f"{index}/{total_points} | Vbias={point.bias_voltage_v:.6g} V | "
            f"Isource={point.source_current_a:.6g} A | Rlockin={_format_optional(point.lockin_r_v, ' V')} | "
            f"theta={_format_optional(point.lockin_theta_deg, ' deg')} | t={elapsed:.3f} s"
        )
    if hasattr(point, "pulse_voltage_v"):
        return (
            f"{index}/{total_points} | pulse={point.pulse_index} | "
            f"Vbase={point.base_voltage_v:.6g} V | Vpulse={point.pulse_voltage_v:.6g} V | "
            f"I={point.source_current_a:.6g} A | t={elapsed:.3f} s"
        )
    return f"{index}/{total_points} | {point}"


def _format_optional(value: float | None, unit: str) -> str:
    return "n/a" if value is None else f"{value:.6g}{unit}"
