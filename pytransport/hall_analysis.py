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


HALL_MOBILITY_COLUMNS = [
    "gate1_voltage_v",
    "gate2_voltage_v",
    "hall_source_kind",
    "hall_carrier_density_per_m2",
    "hall_source_resistance_ohm",
    "hall_antisym_resistance_ohm",
    "hall_zero_corrected_resistance_ohm",
    "field_even_resistance_ohm",
    "longitudinal_sheet_conductivity_s_per_sq",
    "longitudinal_sheet_resistance_ohm_per_sq",
    "mobility_signed_m2_per_v_s",
    "mobility_magnitude_m2_per_v_s",
    "mobility_magnitude_cm2_per_v_s",
]


HALL_ZERO_CORRECTED_COLUMNS = [
    "gate1_voltage_v",
    "gate2_voltage_v",
    "field_value",
    "zero_field_value",
    "field_resistance_ohm",
    "zero_field_resistance_ohm",
    "hall_zero_corrected_resistance_ohm",
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


@dataclass(frozen=True)
class HallMobilityResult:
    output_csv: Path
    report_path: Path
    metadata_path: Path
    points: int
    hall_density_source: Path
    hall_source_kind: str
    longitudinal_run_dir: Path


@dataclass(frozen=True)
class HallZeroCorrectedResult:
    output_csv: Path
    report_path: Path
    metadata_path: Path
    points: int
    magnetic_field_t: float
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


def write_dual_gate_lockin_hall_mobility(
    hall_density_source: str | Path,
    longitudinal_run_dir: str | Path,
    output_dir: str | Path | None = None,
    overwrite: bool = False,
) -> HallMobilityResult:
    hall_source_path = Path(hall_density_source)
    longitudinal_path = Path(longitudinal_run_dir)
    output_path = Path(output_dir) if output_dir is not None else hall_source_path.with_name(
        f"{hall_source_path.name}_mobility"
    )
    if output_path.exists() and any(output_path.iterdir()) and not overwrite:
        raise FileExistsError(f"Output directory already exists and is not empty: {output_path}")
    output_path.mkdir(parents=True, exist_ok=True)

    hall_csv, hall_source_kind = _resolve_hall_density_csv(hall_source_path)
    hall_rows = _read_hall_density_rows(hall_csv, hall_source_kind)
    longitudinal_metadata = read_dual_gate_lockin_metadata(longitudinal_path)
    _validate_longitudinal_metadata(longitudinal_metadata)
    longitudinal_points = read_dual_gate_lockin_points(longitudinal_path)
    longitudinal_by_gate = _points_by_gate(longitudinal_points)

    missing_longitudinal = sorted(set(hall_rows) - set(longitudinal_by_gate))
    if missing_longitudinal:
        raise ValueError(
            "longitudinal run is missing gate points required by Hall antisym data; "
            f"missing={missing_longitudinal[:3]}"
        )

    rows = []
    for key in sorted(hall_rows):
        hall_row = hall_rows[key]
        longitudinal_point = longitudinal_by_gate[key]
        density = hall_row["hall_carrier_density_per_m2"]
        sheet_conductivity = _optional_float(longitudinal_point.get("lockin_sheet_conductivity_s_per_sq"))
        sheet_resistance = _optional_float(longitudinal_point.get("lockin_sheet_resistance_ohm_per_sq"))
        mobility_signed = None
        mobility_magnitude = None
        if density not in {None, 0.0} and sheet_conductivity is not None:
            mobility_signed = sheet_conductivity / (ELEMENTARY_CHARGE_C * density)
            mobility_magnitude = abs(sheet_conductivity) / (ELEMENTARY_CHARGE_C * abs(density))
        rows.append(
            {
                "gate1_voltage_v": key[0],
                "gate2_voltage_v": key[1],
                "hall_source_kind": hall_source_kind,
                "hall_carrier_density_per_m2": density,
                "hall_source_resistance_ohm": hall_row["hall_source_resistance_ohm"],
                "hall_antisym_resistance_ohm": hall_row["hall_antisym_resistance_ohm"],
                "hall_zero_corrected_resistance_ohm": hall_row["hall_zero_corrected_resistance_ohm"],
                "field_even_resistance_ohm": hall_row["field_even_resistance_ohm"],
                "longitudinal_sheet_conductivity_s_per_sq": sheet_conductivity,
                "longitudinal_sheet_resistance_ohm_per_sq": sheet_resistance,
                "mobility_signed_m2_per_v_s": mobility_signed,
                "mobility_magnitude_m2_per_v_s": mobility_magnitude,
                "mobility_magnitude_cm2_per_v_s": None if mobility_magnitude is None else mobility_magnitude * 1.0e4,
            }
        )

    output_csv = output_path / "hall_mobility.csv"
    with output_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=HALL_MOBILITY_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    report_path = output_path / "hall_mobility_report.md"
    report_path.write_text(
        format_hall_mobility_report(hall_csv, longitudinal_path, rows),
        encoding="utf-8",
    )
    metadata_path = output_path / "hall_mobility_metadata.json"
    with metadata_path.open("w", encoding="utf-8") as handle:
        json.dump(
            {
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "hall_density_csv": str(hall_csv),
                "hall_density_source_kind": hall_source_kind,
                "hall_antisym_csv": str(hall_csv) if hall_source_kind == "antisym" else None,
                "hall_zero_corrected_csv": str(hall_csv) if hall_source_kind == "zero_corrected" else None,
                "longitudinal_run_dir": str(longitudinal_path),
                "points": len(rows),
                "output_csv": str(output_csv),
                "report_path": str(report_path),
                "model": "mobility = sheet_conductivity / (e * hall_carrier_density)",
            },
            handle,
            indent=2,
            sort_keys=True,
            default=str,
        )
    return HallMobilityResult(
        output_csv,
        report_path,
        metadata_path,
        len(rows),
        hall_csv,
        hall_source_kind,
        longitudinal_path,
    )


def write_dual_gate_lockin_hall_zero_corrected(
    field_run_dir: str | Path,
    zero_field_run_dir: str | Path,
    output_dir: str | Path | None = None,
    value_column: HallValueColumn = "lockin_x_v",
    overwrite: bool = False,
) -> HallZeroCorrectedResult:
    field_path = Path(field_run_dir)
    zero_path = Path(zero_field_run_dir)
    output_path = Path(output_dir) if output_dir is not None else field_path.with_name(
        f"{field_path.name}_hall_zero_corrected"
    )
    if output_path.exists() and any(output_path.iterdir()) and not overwrite:
        raise FileExistsError(f"Output directory already exists and is not empty: {output_path}")
    output_path.mkdir(parents=True, exist_ok=True)

    field_metadata = read_dual_gate_lockin_metadata(field_path)
    zero_metadata = read_dual_gate_lockin_metadata(zero_path)
    field_b = _validate_hall_zero_pair_metadata(field_metadata, zero_metadata)
    field_points = read_dual_gate_lockin_points(field_path)
    zero_points = read_dual_gate_lockin_points(zero_path)
    field_by_gate = _points_by_gate(field_points)
    zero_by_gate = _points_by_gate(zero_points)
    if set(field_by_gate) != set(zero_by_gate):
        missing_from_zero = sorted(set(field_by_gate) - set(zero_by_gate))
        missing_from_field = sorted(set(zero_by_gate) - set(field_by_gate))
        raise ValueError(
            "field and zero-field runs have different gate grids; "
            f"missing_from_zero={missing_from_zero[:3]}, missing_from_field={missing_from_field[:3]}"
        )

    rows = []
    for key in sorted(field_by_gate):
        field_point = field_by_gate[key]
        zero_point = zero_by_gate[key]
        field_value = _point_value_as_resistance_input(field_point, value_column)
        zero_value = _point_value_as_resistance_input(zero_point, value_column)
        field_resistance = _value_to_resistance(field_value, field_point, value_column)
        zero_resistance = _value_to_resistance(zero_value, zero_point, value_column)
        corrected = None
        density = None
        if field_resistance is not None and zero_resistance is not None:
            corrected = field_resistance - zero_resistance
            if corrected != 0:
                density = field_b / (ELEMENTARY_CHARGE_C * corrected)
        rows.append(
            {
                "gate1_voltage_v": key[0],
                "gate2_voltage_v": key[1],
                "field_value": field_value,
                "zero_field_value": zero_value,
                "field_resistance_ohm": field_resistance,
                "zero_field_resistance_ohm": zero_resistance,
                "hall_zero_corrected_resistance_ohm": corrected,
                "hall_carrier_density_per_m2": density,
            }
        )

    output_csv = output_path / "hall_zero_corrected.csv"
    with output_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=HALL_ZERO_CORRECTED_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    report_path = output_path / "hall_zero_corrected_report.md"
    report_path.write_text(
        format_hall_zero_corrected_report(field_path, zero_path, rows, value_column, field_b),
        encoding="utf-8",
    )
    metadata_path = output_path / "hall_zero_corrected_metadata.json"
    with metadata_path.open("w", encoding="utf-8") as handle:
        json.dump(
            {
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "field_run_dir": str(field_path),
                "zero_field_run_dir": str(zero_path),
                "value_column": value_column,
                "points": len(rows),
                "magnetic_field_t": field_b,
                "output_csv": str(output_csv),
                "report_path": str(report_path),
                "model": "Rxy_corrected = Rxy(B) - Rxy(0); n_2d = B / (e * Rxy_corrected)",
            },
            handle,
            indent=2,
            sort_keys=True,
            default=str,
        )
    return HallZeroCorrectedResult(output_csv, report_path, metadata_path, len(rows), field_b, value_column)


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


def format_hall_zero_corrected_report(
    field_run_dir: str | Path,
    zero_field_run_dir: str | Path,
    rows: list[dict[str, Any]],
    value_column: HallValueColumn,
    magnetic_field_t: float,
) -> str:
    corrected_values = [
        float(row["hall_zero_corrected_resistance_ohm"])
        for row in rows
        if row["hall_zero_corrected_resistance_ohm"] is not None
    ]
    density_values = [float(row["hall_carrier_density_per_m2"]) for row in rows if row["hall_carrier_density_per_m2"] is not None]
    return "\n".join(
        [
            "# Hall Zero-Field Correction Report",
            "",
            f"- Field run: `{field_run_dir}`",
            f"- Zero-field run: `{zero_field_run_dir}`",
            f"- Value column: `{value_column}`",
            f"- Matched gate points: {len(rows)}",
            f"- B: {_fmt(magnetic_field_t, ' T')}",
            f"- Corrected Hall resistance range: {_fmt(min(corrected_values) if corrected_values else None, ' ohm')} to {_fmt(max(corrected_values) if corrected_values else None, ' ohm')}",
            f"- Hall carrier density range: {_fmt(min(density_values) if density_values else None, ' m^-2')} to {_fmt(max(density_values) if density_values else None, ' m^-2')}",
            "",
            "## Model",
            "",
            "`Rxy_corrected = Rxy(B) - Rxy(0)`",
            "",
            "`n_2d = B / (e * Rxy_corrected)`",
            "",
            "Use antisymmetrization when matched `+B` and `-B` runs are available; use zero-field correction when the saved measurement set contains a reliable `B=0` Hall offset run.",
            "",
        ]
    )


def format_hall_mobility_report(
    hall_density_csv: str | Path,
    longitudinal_run_dir: str | Path,
    rows: list[dict[str, Any]],
) -> str:
    density_values = [float(row["hall_carrier_density_per_m2"]) for row in rows if row["hall_carrier_density_per_m2"] is not None]
    conductivity_values = [
        float(row["longitudinal_sheet_conductivity_s_per_sq"])
        for row in rows
        if row["longitudinal_sheet_conductivity_s_per_sq"] is not None
    ]
    mobility_values = [
        float(row["mobility_magnitude_cm2_per_v_s"])
        for row in rows
        if row["mobility_magnitude_cm2_per_v_s"] is not None
    ]
    return "\n".join(
        [
            "# Hall Mobility Report",
            "",
            f"- Hall density CSV: `{hall_density_csv}`",
            f"- Hall source kind: `{rows[0]['hall_source_kind'] if rows else 'n/a'}`",
            f"- Longitudinal Vxx run: `{longitudinal_run_dir}`",
            f"- Matched gate points: {len(rows)}",
            f"- Hall carrier density range: {_fmt(min(density_values) if density_values else None, ' m^-2')} to {_fmt(max(density_values) if density_values else None, ' m^-2')}",
            f"- Sheet conductivity range: {_fmt(min(conductivity_values) if conductivity_values else None, ' S/sq')} to {_fmt(max(conductivity_values) if conductivity_values else None, ' S/sq')}",
            f"- Mobility magnitude range: {_fmt(min(mobility_values) if mobility_values else None, ' cm^2/V/s')} to {_fmt(max(mobility_values) if mobility_values else None, ' cm^2/V/s')}",
            "",
            "## Model",
            "",
            "`mu_signed = sigma_sheet / (e * n_2d)`",
            "",
            "`|mu| = |sigma_sheet| / (e * |n_2d|)`",
            "",
            "The signed mobility follows the Hall-density sign convention; the magnitude column is usually the lab-facing value.",
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


def _validate_hall_zero_pair_metadata(field_metadata: dict[str, Any], zero_metadata: dict[str, Any]) -> float:
    for label, metadata in [("field", field_metadata), ("zero-field", zero_metadata)]:
        if metadata.get("measurement_type") != "dual_gate_lockin_sweep":
            raise ValueError(f"{label} run is not a dual_gate_lockin_sweep")
        if metadata.get("completed") is not True:
            raise ValueError(f"{label} run is not completed")
        if metadata.get("voltage_probe_role") != "hall":
            raise ValueError(f"{label} run voltage_probe_role must be hall")
    field_b = _optional_float(field_metadata.get("magnetic_field_t"))
    zero_b = _optional_float(zero_metadata.get("magnetic_field_t"))
    if field_b is None or _close(field_b, 0.0):
        raise ValueError("field run must include nonzero magnetic_field_t")
    if zero_b is None:
        raise ValueError("zero-field run must include magnetic_field_t")
    if not _close(zero_b, 0.0):
        raise ValueError("zero-field run magnetic_field_t must be 0")
    return field_b


def _validate_longitudinal_metadata(metadata: dict[str, Any]) -> None:
    if metadata.get("measurement_type") != "dual_gate_lockin_sweep":
        raise ValueError("longitudinal run is not a dual_gate_lockin_sweep")
    if metadata.get("completed") is not True:
        raise ValueError("longitudinal run is not completed")
    if metadata.get("voltage_probe_role") != "longitudinal":
        raise ValueError("longitudinal run voltage_probe_role must be longitudinal")


def _resolve_hall_density_csv(path: Path) -> tuple[Path, str]:
    if path.is_dir():
        antisym = path / "hall_antisym.csv"
        zero_corrected = path / "hall_zero_corrected.csv"
        if antisym.exists() and zero_corrected.exists():
            raise ValueError(f"{path} contains both hall_antisym.csv and hall_zero_corrected.csv; pass one CSV path")
        if antisym.exists():
            return antisym, "antisym"
        if zero_corrected.exists():
            return zero_corrected, "zero_corrected"
        raise FileNotFoundError(f"Missing Hall density CSV in {path}: expected hall_antisym.csv or hall_zero_corrected.csv")
    if path.name == "hall_zero_corrected.csv":
        return path, "zero_corrected"
    if path.name == "hall_antisym.csv":
        return path, "antisym"
    return path, _infer_hall_density_csv_kind(path)


def _infer_hall_density_csv_kind(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Missing Hall density CSV: {path}")
    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fields = set(reader.fieldnames or [])
    if "hall_antisym_resistance_ohm" in fields:
        return "antisym"
    if "hall_zero_corrected_resistance_ohm" in fields:
        return "zero_corrected"
    raise ValueError(f"{path} is not a supported Hall density CSV")


def _read_hall_density_rows(path: Path, source_kind: str) -> dict[tuple[float, float], dict[str, float | str | None]]:
    if source_kind == "antisym":
        return _read_hall_antisym_rows(path)
    if source_kind == "zero_corrected":
        return _read_hall_zero_corrected_rows(path)
    raise ValueError(f"unsupported Hall density source kind: {source_kind}")


def _read_hall_antisym_rows(path: Path) -> dict[tuple[float, float], dict[str, float | str | None]]:
    if not path.exists():
        raise FileNotFoundError(f"Missing Hall antisym CSV: {path}")
    rows: dict[tuple[float, float], dict[str, float | str | None]] = {}
    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = set(HALL_ANTISYM_COLUMNS) - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{path} is not a Hall antisym CSV; missing {sorted(missing)}")
        for row in reader:
            key = (float(row["gate1_voltage_v"]), float(row["gate2_voltage_v"]))
            if key in rows:
                raise ValueError(f"duplicate Hall antisym gate point: {key}")
            rows[key] = {
                "hall_source_kind": "antisym",
                "hall_carrier_density_per_m2": _csv_float(row["hall_carrier_density_per_m2"]),
                "hall_source_resistance_ohm": _csv_float(row["hall_antisym_resistance_ohm"]),
                "hall_antisym_resistance_ohm": _csv_float(row["hall_antisym_resistance_ohm"]),
                "hall_zero_corrected_resistance_ohm": None,
                "field_even_resistance_ohm": _csv_float(row["field_even_resistance_ohm"]),
            }
    return rows


def _read_hall_zero_corrected_rows(path: Path) -> dict[tuple[float, float], dict[str, float | str | None]]:
    if not path.exists():
        raise FileNotFoundError(f"Missing Hall zero-corrected CSV: {path}")
    rows: dict[tuple[float, float], dict[str, float | str | None]] = {}
    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = set(HALL_ZERO_CORRECTED_COLUMNS) - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{path} is not a Hall zero-corrected CSV; missing {sorted(missing)}")
        for row in reader:
            key = (float(row["gate1_voltage_v"]), float(row["gate2_voltage_v"]))
            if key in rows:
                raise ValueError(f"duplicate Hall zero-corrected gate point: {key}")
            rows[key] = {
                "hall_source_kind": "zero_corrected",
                "hall_carrier_density_per_m2": _csv_float(row["hall_carrier_density_per_m2"]),
                "hall_source_resistance_ohm": _csv_float(row["hall_zero_corrected_resistance_ohm"]),
                "hall_antisym_resistance_ohm": None,
                "hall_zero_corrected_resistance_ohm": _csv_float(row["hall_zero_corrected_resistance_ohm"]),
                "field_even_resistance_ohm": None,
            }
    return rows


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
    return None if value in {None, ""} else float(value)


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
    if value == "":
        return None
    return float(value)


def _csv_float(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def _close(left: float, right: float) -> bool:
    return abs(left - right) <= max(1e-12, 1e-9 * max(abs(left), abs(right)))


def _fmt(value: float | None, suffix: str = "") -> str:
    if value is None:
        return "n/a"
    return f"{value:.6g}{suffix}"
