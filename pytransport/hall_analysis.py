"""Hall-bar analysis helpers for paired +B/-B dual-gate lock-in runs."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from .dual_gate_lockin import ELEMENTARY_CHARGE_C
from .dual_gate_lockin_review import read_dual_gate_lockin_metadata, read_dual_gate_lockin_points


HallValueColumn = Literal["lockin_x_v", "lockin_y_v", "lockin_r_v", "lockin_hall_resistance_ohm"]


HALL_ANTISYM_COLUMNS = [
    "gate1_voltage_v",
    "gate2_voltage_v",
    "positive_value",
    "negative_value",
    "positive_resistance_ohm",
    "negative_resistance_ohm",
    "hall_antisym_resistance_ohm",
    "field_even_resistance_ohm",
    "hall_carrier_density_per_m2",
]


@dataclass(frozen=True)
class HallAntisymResult:
    output_csv: Path
    report_path: Path
    metadata_path: Path
    points: int
    magnetic_field_abs_t: float | None
    value_column: HallValueColumn


def write_dual_gate_lockin_hall_antisym(
    positive_run_dir: str | Path,
    negative_run_dir: str | Path,
    output_dir: str | Path | None = None,
    value_column: HallValueColumn = "lockin_x_v",
    overwrite: bool = False,
) -> HallAntisymResult:
    positive_path = Path(positive_run_dir)
    negative_path = Path(negative_run_dir)
    output_path = Path(output_dir) if output_dir is not None else positive_path.with_name(
        f"{positive_path.name}_hall_antisym"
    )
    if output_path.exists() and any(output_path.iterdir()) and not overwrite:
        raise FileExistsError(f"Output directory already exists and is not empty: {output_path}")
    output_path.mkdir(parents=True, exist_ok=True)

    positive_metadata = read_dual_gate_lockin_metadata(positive_path)
    negative_metadata = read_dual_gate_lockin_metadata(negative_path)
    _validate_hall_pair_metadata(positive_metadata, negative_metadata)
    positive_points = read_dual_gate_lockin_points(positive_path)
    negative_points = read_dual_gate_lockin_points(negative_path)

    positive_by_gate = _points_by_gate(positive_points)
    negative_by_gate = _points_by_gate(negative_points)
    if set(positive_by_gate) != set(negative_by_gate):
        missing_from_negative = sorted(set(positive_by_gate) - set(negative_by_gate))
        missing_from_positive = sorted(set(negative_by_gate) - set(positive_by_gate))
        raise ValueError(
            "positive and negative runs have different gate grids; "
            f"missing_from_negative={missing_from_negative[:3]}, missing_from_positive={missing_from_positive[:3]}"
        )

    positive_field = _optional_float(positive_metadata.get("magnetic_field_t"))
    negative_field = _optional_float(negative_metadata.get("magnetic_field_t"))
    field_abs = abs(positive_field) if positive_field is not None else None
    rows = []
    for key in sorted(positive_by_gate):
        positive_point = positive_by_gate[key]
        negative_point = negative_by_gate[key]
        positive_value = _point_value_as_resistance_input(positive_point, value_column)
        negative_value = _point_value_as_resistance_input(negative_point, value_column)
        positive_resistance = _value_to_resistance(positive_value, positive_point, value_column)
        negative_resistance = _value_to_resistance(negative_value, negative_point, value_column)
        hall_odd = None
        field_even = None
        density = None
        if positive_resistance is not None and negative_resistance is not None:
            hall_odd = 0.5 * (positive_resistance - negative_resistance)
            field_even = 0.5 * (positive_resistance + negative_resistance)
            if field_abs is not None and hall_odd != 0:
                density = field_abs / (ELEMENTARY_CHARGE_C * hall_odd)
        rows.append(
            {
                "gate1_voltage_v": key[0],
                "gate2_voltage_v": key[1],
                "positive_value": positive_value,
                "negative_value": negative_value,
                "positive_resistance_ohm": positive_resistance,
                "negative_resistance_ohm": negative_resistance,
                "hall_antisym_resistance_ohm": hall_odd,
                "field_even_resistance_ohm": field_even,
                "hall_carrier_density_per_m2": density,
            }
        )

    output_csv = output_path / "hall_antisym.csv"
    with output_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=HALL_ANTISYM_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    report_path = output_path / "hall_antisym_report.md"
    report_path.write_text(
        format_hall_antisym_report(
            positive_path,
            negative_path,
            rows,
            value_column,
            field_abs,
        ),
        encoding="utf-8",
    )
    metadata_path = output_path / "hall_antisym_metadata.json"
    with metadata_path.open("w", encoding="utf-8") as handle:
        json.dump(
            {
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "positive_run_dir": str(positive_path),
                "negative_run_dir": str(negative_path),
                "value_column": value_column,
                "points": len(rows),
                "magnetic_field_abs_t": field_abs,
                "output_csv": str(output_csv),
                "report_path": str(report_path),
            },
            handle,
            indent=2,
            sort_keys=True,
            default=str,
        )
    return HallAntisymResult(output_csv, report_path, metadata_path, len(rows), field_abs, value_column)


def format_hall_antisym_report(
    positive_run_dir: str | Path,
    negative_run_dir: str | Path,
    rows: list[dict[str, Any]],
    value_column: HallValueColumn,
    magnetic_field_abs_t: float | None,
) -> str:
    hall_values = [float(row["hall_antisym_resistance_ohm"]) for row in rows if row["hall_antisym_resistance_ohm"] is not None]
    density_values = [float(row["hall_carrier_density_per_m2"]) for row in rows if row["hall_carrier_density_per_m2"] is not None]
    return "\n".join(
        [
            "# Hall Antisymmetrization Report",
            "",
            f"- Positive-field run: `{positive_run_dir}`",
            f"- Negative-field run: `{negative_run_dir}`",
            f"- Value column: `{value_column}`",
            f"- Matched gate points: {len(rows)}",
            f"- |B|: {_fmt(magnetic_field_abs_t, ' T')}",
            f"- Hall antisym resistance range: {_fmt(min(hall_values) if hall_values else None, ' ohm')} to {_fmt(max(hall_values) if hall_values else None, ' ohm')}",
            f"- Hall carrier density range: {_fmt(min(density_values) if density_values else None, ' m^-2')} to {_fmt(max(density_values) if density_values else None, ' m^-2')}",
            "",
            "## Model",
            "",
            "`Rxy_odd = (R(+B) - R(-B)) / 2`",
            "",
            "`R_even = (R(+B) + R(-B)) / 2`",
            "",
            "`n_2d = |B| / (e * Rxy_odd)`",
            "",
            "The sign of `n_2d` follows the sign of `Rxy_odd`.",
            "",
        ]
    )


def _validate_hall_pair_metadata(positive_metadata: dict[str, Any], negative_metadata: dict[str, Any]) -> None:
    positive_field = _optional_float(positive_metadata.get("magnetic_field_t"))
    negative_field = _optional_float(negative_metadata.get("magnetic_field_t"))
    if positive_field is None or negative_field is None:
        raise ValueError("both runs must include magnetic_field_t metadata")
    if positive_field <= 0 or negative_field >= 0:
        raise ValueError("expected positive_run magnetic_field_t > 0 and negative_run magnetic_field_t < 0")
    if not _close(abs(positive_field), abs(negative_field)):
        raise ValueError("positive and negative runs must use equal |magnetic_field_t|")
    for label, metadata in [("positive", positive_metadata), ("negative", negative_metadata)]:
        if metadata.get("measurement_type") != "dual_gate_lockin_sweep":
            raise ValueError(f"{label} run is not a dual_gate_lockin_sweep")
        if metadata.get("completed") is not True:
            raise ValueError(f"{label} run is not completed")
        if metadata.get("voltage_probe_role") != "hall":
            raise ValueError(f"{label} run voltage_probe_role must be hall")


def _points_by_gate(points: list[dict[str, Any]]) -> dict[tuple[float, float], dict[str, Any]]:
    by_gate: dict[tuple[float, float], dict[str, Any]] = {}
    for point in points:
        key = (float(point["gate1_voltage_v"]), float(point["gate2_voltage_v"]))
        if key in by_gate:
            raise ValueError(f"duplicate gate point: {key}")
        by_gate[key] = point
    return by_gate


def _point_value_as_resistance_input(point: dict[str, Any], value_column: HallValueColumn) -> float | None:
    value = point.get(value_column)
    return None if value is None else float(value)


def _value_to_resistance(value: float | None, point: dict[str, Any], value_column: HallValueColumn) -> float | None:
    if value is None:
        return None
    if value_column == "lockin_hall_resistance_ohm":
        return value
    nominal_current = point.get("source_drain_nominal_current_a")
    if nominal_current in {None, 0.0}:
        return None
    return float(value) / float(nominal_current)


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _close(left: float, right: float) -> bool:
    return abs(left - right) <= max(1e-12, 1e-9 * max(abs(left), abs(right)))


def _fmt(value: float | None, suffix: str = "") -> str:
    if value is None:
        return "n/a"
    return f"{value:.6g}{suffix}"

