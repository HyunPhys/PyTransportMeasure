"""Dual-gate lock-in sweep runner.

Current milestone: dry-run execution for two Keithley gate biases plus SR860
lock-in readout. Hardware execution remains CLI-blocked until SR860 excitation
and wiring are smoke-tested.
"""

from __future__ import annotations

import csv
import hashlib
import json
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import yaml

from .batch import safe_name
from .errors import SafetyLimitError
from .instruments.base import LockInAmplifier, SourceMeasureUnit
from .io import unique_run_dir
from .lockin_timing import lockin_read_settle_s, lockin_time_constant_s
from .lockin_settings import (
    compare_lockin_settings,
    lockin_setting_checks_to_dicts,
    lockin_settings_ok,
    lockin_settings_readback_available,
    raise_for_lockin_settings_mismatch,
)
from .output_state import (
    all_outputs_off_after_run,
    any_output_enabled,
    command_voltage_with_state,
    initialize_output_state,
    output_off_with_state,
    output_on_with_state,
    zero_before_off_with_state,
)
from .recipes import DualGateLockInRecipe, SafetyPreset, gate_voltages_from_config
from .safety import validate_dual_gate_lockin_recipe_against_safety, validate_point_current
from .smu_config import (
    build_voltage_source_config,
    compare_voltage_source_config_readback,
    raise_for_voltage_source_config_readback_mismatch,
    read_voltage_source_config_if_available,
    voltage_source_config_snapshot,
)
from .ac_lockin import format_lockin_settings


ELEMENTARY_CHARGE_C = 1.602176634e-19


DUAL_GATE_LOCKIN_COLUMNS = [
    "index",
    "gate1_index",
    "gate2_index",
    "gate1_voltage_v",
    "gate2_voltage_v",
    "gate1_current_a",
    "gate2_current_a",
    "elapsed_s",
    "gate1_compliance_hit",
    "gate2_compliance_hit",
    "lockin_x_v",
    "lockin_y_v",
    "lockin_r_v",
    "lockin_theta_deg",
    "source_drain_excitation_v",
    "source_drain_nominal_current_a",
    "lockin_resistance_ohm",
    "lockin_conductance_s",
    "lockin_sheet_resistance_ohm_per_sq",
    "lockin_sheet_conductivity_s_per_sq",
    "lockin_hall_resistance_ohm",
    "lockin_hall_carrier_density_per_m2",
]


@dataclass(frozen=True)
class DualGateLockInPoint:
    index: int
    gate1_index: int
    gate2_index: int
    gate1_voltage_v: float
    gate2_voltage_v: float
    gate1_current_a: float
    gate2_current_a: float
    elapsed_s: float
    gate1_compliance_hit: bool
    gate2_compliance_hit: bool
    lockin_x_v: float | None
    lockin_y_v: float | None
    lockin_r_v: float | None
    lockin_theta_deg: float | None
    source_drain_excitation_v: float | None = None
    source_drain_nominal_current_a: float | None = None
    lockin_resistance_ohm: float | None = None
    lockin_conductance_s: float | None = None
    lockin_sheet_resistance_ohm_per_sq: float | None = None
    lockin_sheet_conductivity_s_per_sq: float | None = None
    lockin_hall_resistance_ohm: float | None = None
    lockin_hall_carrier_density_per_m2: float | None = None

    def to_dict(self) -> dict[str, float | int | bool | None]:
        return asdict(self)


class DualGateLockInRunWriter:
    def __init__(self, output_dir: Path, measurement_name: str, resume_rows: list[dict[str, str]] | None = None):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.run_dir = unique_run_dir(output_dir, f"{timestamp}_{safe_name(measurement_name)}")
        self.run_dir.mkdir(parents=True, exist_ok=False)
        self.csv_path = self.run_dir / "points.csv"
        self.metadata_path = self.run_dir / "metadata.json"
        self.recipe_snapshot_path = self.run_dir / "recipe_snapshot.yaml"
        self.safety_snapshot_path = self.run_dir / "safety_snapshot.yaml"
        self._csv_file = self.csv_path.open("w", newline="", encoding="utf-8")
        self._writer = csv.DictWriter(self._csv_file, fieldnames=DUAL_GATE_LOCKIN_COLUMNS)
        self._writer.writeheader()
        for row in resume_rows or []:
            self._writer.writerow({column: row.get(column, "") for column in DUAL_GATE_LOCKIN_COLUMNS})
        self._csv_file.flush()

    def write_point(self, point: DualGateLockInPoint) -> None:
        self._writer.writerow(point.to_dict())
        self._csv_file.flush()

    def write_metadata(self, metadata: dict[str, Any]) -> None:
        with self.metadata_path.open("w", encoding="utf-8") as handle:
            json.dump(metadata, handle, indent=2, sort_keys=True, default=str)

    def write_yaml_snapshot(self, path: Path, data: dict[str, Any]) -> None:
        with path.open("w", encoding="utf-8") as handle:
            yaml.safe_dump(data, handle, sort_keys=False)

    def close(self) -> None:
        self._csv_file.close()


def dual_gate_lockin_point_count(recipe: DualGateLockInRecipe) -> int:
    return len(gate_voltages_from_config(recipe.gate1_sweep)) * len(gate_voltages_from_config(recipe.gate2_sweep))


def planned_dual_gate_lockin_grid(recipe: DualGateLockInRecipe) -> list[dict[str, float | int]]:
    gate1_voltages = gate_voltages_from_config(recipe.gate1_sweep)
    gate2_voltages = gate_voltages_from_config(recipe.gate2_sweep)
    return [
        {
            "index": gate1_index * len(gate2_voltages) + gate2_index,
            "gate1_index": gate1_index,
            "gate2_index": gate2_index,
            "gate1_voltage_v": float(gate1_voltage_v),
            "gate2_voltage_v": float(gate2_voltage_v),
        }
        for gate1_index, gate1_voltage_v in enumerate(gate1_voltages)
        for gate2_index, gate2_voltage_v in enumerate(gate2_voltages)
    ]


def dual_gate_lockin_grid_signature(recipe: DualGateLockInRecipe) -> str:
    grid = planned_dual_gate_lockin_grid(recipe)
    payload = json.dumps(grid, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class DualGateLockInResumeState:
    source_run_dir: Path
    source_metadata_path: Path
    source_csv_path: Path
    copied_rows: tuple[dict[str, str], ...]
    next_point_index: int
    source_points_written: int
    source_last_completed_index: int | None


@dataclass(frozen=True)
class DualGateLockInResumeCheck:
    recipe_path: Path
    source_run_dir: Path
    ok: bool
    message: str
    planned_points: int
    copied_points: int
    remaining_points: int
    next_point_index: int | None
    next_gate1_index: int | None
    next_gate2_index: int | None
    next_gate1_voltage_v: float | None
    next_gate2_voltage_v: float | None
    grid_signature: str


def check_dual_gate_lockin_resume(
    recipe: DualGateLockInRecipe,
    recipe_path: str | Path,
    run_dir: str | Path,
) -> DualGateLockInResumeCheck:
    planned_grid = planned_dual_gate_lockin_grid(recipe)
    planned_points = len(planned_grid)
    grid_signature = dual_gate_lockin_grid_signature(recipe)
    try:
        state = load_dual_gate_lockin_resume_state(run_dir, recipe)
    except ValueError as exc:
        return DualGateLockInResumeCheck(
            recipe_path=Path(recipe_path),
            source_run_dir=Path(run_dir),
            ok=False,
            message=str(exc),
            planned_points=planned_points,
            copied_points=0,
            remaining_points=planned_points,
            next_point_index=None,
            next_gate1_index=None,
            next_gate2_index=None,
            next_gate1_voltage_v=None,
            next_gate2_voltage_v=None,
            grid_signature=grid_signature,
        )
    next_point = planned_grid[state.next_point_index]
    return DualGateLockInResumeCheck(
        recipe_path=Path(recipe_path),
        source_run_dir=state.source_run_dir,
        ok=True,
        message="resume source is compatible",
        planned_points=planned_points,
        copied_points=len(state.copied_rows),
        remaining_points=planned_points - len(state.copied_rows),
        next_point_index=state.next_point_index,
        next_gate1_index=int(next_point["gate1_index"]),
        next_gate2_index=int(next_point["gate2_index"]),
        next_gate1_voltage_v=float(next_point["gate1_voltage_v"]),
        next_gate2_voltage_v=float(next_point["gate2_voltage_v"]),
        grid_signature=grid_signature,
    )


def format_dual_gate_lockin_resume_check(report: DualGateLockInResumeCheck) -> str:
    lines = [
        f"Dual-gate lock-in resume check: {'PASS' if report.ok else 'FAIL'}",
        f"Recipe: {report.recipe_path}",
        f"Source run: {report.source_run_dir}",
        f"Message: {report.message}",
        f"Grid signature: {report.grid_signature}",
        f"Planned points: {report.planned_points}",
        f"Copied points: {report.copied_points}",
        f"Remaining points: {report.remaining_points}",
    ]
    if report.next_point_index is not None:
        lines.extend(
            [
                f"Next point index: {report.next_point_index}",
                f"Next gate indices: gate1={report.next_gate1_index}, gate2={report.next_gate2_index}",
                (
                    "Next gate voltages: "
                    f"Vg1={report.next_gate1_voltage_v:.6g} V, "
                    f"Vg2={report.next_gate2_voltage_v:.6g} V"
                ),
            ]
        )
    return "\n".join(lines)


def load_dual_gate_lockin_resume_state(
    run_dir: str | Path,
    recipe: DualGateLockInRecipe,
) -> DualGateLockInResumeState:
    source_run_dir = Path(run_dir)
    metadata_path = source_run_dir / "metadata.json"
    csv_path = source_run_dir / "points.csv"
    if not metadata_path.exists():
        raise ValueError(f"Resume metadata not found: {metadata_path}")
    if not csv_path.exists():
        raise ValueError(f"Resume points CSV not found: {csv_path}")
    with metadata_path.open("r", encoding="utf-8") as handle:
        metadata = json.load(handle)
    if metadata.get("measurement_type") != "dual_gate_lockin_sweep":
        raise ValueError("Resume source is not a dual_gate_lockin_sweep run")
    if metadata.get("completed") is True:
        raise ValueError("Resume source is already completed; use the completed run directly")
    expected_signature = dual_gate_lockin_grid_signature(recipe)
    actual_signature = metadata.get("planned_gate_grid_signature")
    if actual_signature != expected_signature:
        raise ValueError("Resume source grid signature does not match the current recipe")
    with csv_path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
    indices: list[int] = []
    for row in rows:
        try:
            indices.append(int(row["index"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("Resume points CSV contains a row without a valid integer index") from exc
    expected_indices = list(range(len(rows)))
    if indices != expected_indices:
        raise ValueError("Resume points CSV must contain a contiguous prefix starting at index 0")
    planned_points = dual_gate_lockin_point_count(recipe)
    if len(rows) >= planned_points:
        raise ValueError("Resume source already contains all planned points")
    source_last_completed_index = metadata.get("last_completed_index")
    if source_last_completed_index is not None:
        source_last_completed_index = int(source_last_completed_index)
    return DualGateLockInResumeState(
        source_run_dir=source_run_dir,
        source_metadata_path=metadata_path,
        source_csv_path=csv_path,
        copied_rows=tuple(rows),
        next_point_index=len(rows),
        source_points_written=int(metadata.get("points_written") or len(rows)),
        source_last_completed_index=source_last_completed_index,
    )


def format_dual_gate_lockin_plan(
    recipe: DualGateLockInRecipe,
    safety: SafetyPreset,
    recipe_path: str | Path,
    preview_points: int = 5,
) -> str:
    gate1_voltages = gate_voltages_from_config(recipe.gate1_sweep)
    gate2_voltages = gate_voltages_from_config(recipe.gate2_sweep)
    lines = [
        f"Dual-Gate Lock-In Sweep Plan: {recipe.measurement_name}",
        f"Recipe: {Path(recipe_path)}",
        f"Measurement geometry: {format_geometry(recipe.measurement_geometry.model_dump(mode='json'))}",
        f"Safety preset: {safety.name}",
        f"Gate1 instrument: {recipe.gate1_instrument.id} at {recipe.gate1_instrument.address}",
        f"Gate2 instrument: {recipe.gate2_instrument.id} at {recipe.gate2_instrument.address}",
        f"Gate1 NPLC: {recipe.gate1_instrument.nplc if recipe.gate1_instrument.nplc is not None else 'auto'}",
        f"Gate2 NPLC: {recipe.gate2_instrument.nplc if recipe.gate2_instrument.nplc is not None else 'auto'}",
        f"Gate1 source delay: {recipe.gate1_instrument.source_delay_s if recipe.gate1_instrument.source_delay_s is not None else 'auto'} s",
        f"Gate2 source delay: {recipe.gate2_instrument.source_delay_s if recipe.gate2_instrument.source_delay_s is not None else 'auto'} s",
        f"Lock-in: {recipe.lockin.id} at {recipe.lockin.address}",
        f"Lock-in channels: {', '.join(recipe.lockin.channels)}",
        f"Lock-in timing: {recipe.lockin.read_timing}",
        *format_lockin_settings(recipe.lockin.model_dump(mode="json")),
        *format_topology_settings(recipe.topology.model_dump(mode="json")),
        f"Gate1 sweep: {gate1_voltages[0]:.6g} V -> {gate1_voltages[-1]:.6g} V, {len(gate1_voltages)} points, settle {recipe.gate1_sweep.settle_s:.6g} s",
        f"Gate2 sweep: {gate2_voltages[0]:.6g} V -> {gate2_voltages[-1]:.6g} V, {len(gate2_voltages)} points, settle {recipe.gate2_sweep.settle_s:.6g} s",
        f"Total points: {len(gate1_voltages) * len(gate2_voltages)}",
        f"Gate1 compliance: {recipe.gate1_sweep.current_compliance_a:.6g} A",
        f"Gate2 compliance: {recipe.gate2_sweep.current_compliance_a:.6g} A",
        f"Safety current limit: {safety.max_abs_current_a:.6g} A",
        *format_dual_gate_lockin_scan_readiness(recipe),
    ]
    preview = max(0, preview_points)
    if preview:
        pairs = [(gate1_v, gate2_v) for gate1_v in gate1_voltages for gate2_v in gate2_voltages]
        head = pairs[:preview]
        tail = pairs[-preview:] if len(pairs) > preview else []
        lines.append("Preview points:")
        for index, (gate1_v, gate2_v) in enumerate(head):
            lines.append(f"  #{index}: Vg1={gate1_v:.6g} V, Vg2={gate2_v:.6g} V")
        if tail and tail[0] != head[0]:
            if len(pairs) > 2 * preview:
                lines.append("  ...")
            start_index = len(pairs) - len(tail)
            for offset, (gate1_v, gate2_v) in enumerate(tail):
                lines.append(f"  #{start_index + offset}: Vg1={gate1_v:.6g} V, Vg2={gate2_v:.6g} V")
    return "\n".join(lines)


def format_dual_gate_lockin_scan_readiness(
    recipe: DualGateLockInRecipe,
    max_hardware_points: int = 9,
) -> list[str]:
    gate1_voltages = gate_voltages_from_config(recipe.gate1_sweep)
    gate2_voltages = gate_voltages_from_config(recipe.gate2_sweep)
    total_points = len(gate1_voltages) * len(gate2_voltages)
    gate1_step = voltage_step(gate1_voltages)
    gate2_step = voltage_step(gate2_voltages)
    lockin_settle_s = lockin_read_settle_s(recipe.lockin)
    minimum_settle_s = (
        len(gate1_voltages) * recipe.gate1_sweep.settle_s
        + total_points * (recipe.gate2_sweep.settle_s + lockin_settle_s)
    )
    topology = recipe.topology.model_dump(mode="json")
    nominal_current = nominal_source_drain_current_a(topology)
    lines = [
        "Scan readiness:",
        f"  Gate grid: {len(gate1_voltages)} x {len(gate2_voltages)} = {total_points} points",
        f"  Gate1 step: {format_step(gate1_step)}",
        f"  Gate2 step: {format_step(gate2_step)}",
        f"  Lock-in read settle per point: {lockin_settle_s:.6g} s",
        f"  Minimum programmed settle time: {minimum_settle_s:.6g} s",
        f"  Default hardware point guard: {max_hardware_points} points",
        f"  Within default point guard: {total_points <= max_hardware_points}",
    ]
    if nominal_current is not None:
        lines.append(f"  Nominal source-drain AC current: {nominal_current:.6g} A")
    else:
        lines.append("  Nominal source-drain AC current: n/a")
    return lines


def voltage_step(voltages: list[float]) -> float | None:
    if len(voltages) < 2:
        return None
    return float(voltages[1]) - float(voltages[0])


def format_step(step: float | None) -> str:
    if step is None:
        return "n/a"
    return f"{step:.6g} V"


def format_geometry(geometry: dict) -> str:
    method = geometry.get("method") or "two_terminal"
    terminal_count = geometry.get("terminal_count") or 2
    notes = geometry.get("notes")
    text = f"{method}, {terminal_count}-terminal"
    return f"{text}, {notes}" if notes else text


def format_topology_settings(topology: dict[str, Any]) -> list[str]:
    lines = [
        f"Topology layout: {topology.get('device_layout')}",
        f"Gate roles: gate1={topology.get('gate1_role')}, gate2={topology.get('gate2_role')}",
        f"Source/drain contacts: {topology.get('source_contact')} -> {topology.get('drain_contact')}",
        f"Lock-in input: {topology.get('lockin_input_mode')} on {', '.join(topology.get('lockin_input_contacts') or [])}",
        f"Voltage probe role: {topology.get('voltage_probe_role') or 'generic'}",
        f"Excitation source: {topology.get('excitation_source')}",
    ]
    channel_length = topology.get("channel_length_m")
    channel_width = topology.get("channel_width_m")
    if channel_length is not None and channel_width is not None:
        lines.append(f"Channel geometry: L={channel_length} m, W={channel_width} m")
    magnetic_field = topology.get("magnetic_field_t")
    if magnetic_field is not None:
        lines.append(f"Magnetic field: {magnetic_field} T")
    excitation_contacts = topology.get("excitation_contacts") or []
    if excitation_contacts:
        lines.append(f"Excitation contacts: {', '.join(excitation_contacts)}")
    excitation_amplitude = topology.get("excitation_amplitude_v")
    if excitation_amplitude is not None:
        lines.append(f"Excitation amplitude: {excitation_amplitude} V")
    bias_resistor = topology.get("current_bias_resistor_ohm")
    if bias_resistor is not None:
        lines.append(f"Current-bias resistor: {bias_resistor} ohm")
    nominal_current = nominal_source_drain_current_a(topology)
    if nominal_current is not None:
        lines.append(f"Nominal source-drain AC current: {nominal_current:.6g} A")
    notes = topology.get("notes")
    if notes:
        lines.append(f"Topology notes: {notes}")
    return lines


def nominal_source_drain_current_a(topology: dict[str, Any]) -> float | None:
    amplitude = topology.get("excitation_amplitude_v")
    bias_resistor = topology.get("current_bias_resistor_ohm")
    if amplitude is None or bias_resistor is None:
        return None
    if bias_resistor == 0:
        return None
    return float(amplitude) / float(bias_resistor)


def derive_lockin_transport_values(
    lockin_r_v: float | None,
    topology: dict[str, Any],
) -> dict[str, float | None]:
    excitation_v = topology.get("excitation_amplitude_v")
    nominal_current_a = nominal_source_drain_current_a(topology)
    resistance_ohm = None
    conductance_s = None
    sheet_resistance_ohm_per_sq = None
    sheet_conductivity_s_per_sq = None
    hall_resistance_ohm = None
    hall_carrier_density_per_m2 = None
    if lockin_r_v is not None and nominal_current_a not in {None, 0.0}:
        resistance_ohm = float(lockin_r_v) / float(nominal_current_a)
        if resistance_ohm != 0:
            conductance_s = 1.0 / resistance_ohm
        if topology.get("voltage_probe_role") == "longitudinal":
            channel_length = topology.get("channel_length_m")
            channel_width = topology.get("channel_width_m")
            if channel_length is not None and channel_width is not None:
                sheet_resistance_ohm_per_sq = resistance_ohm * float(channel_width) / float(channel_length)
                if sheet_resistance_ohm_per_sq != 0:
                    sheet_conductivity_s_per_sq = 1.0 / sheet_resistance_ohm_per_sq
        if topology.get("voltage_probe_role") == "hall":
            hall_resistance_ohm = resistance_ohm
            magnetic_field_t = topology.get("magnetic_field_t")
            if magnetic_field_t is not None and hall_resistance_ohm != 0:
                hall_carrier_density_per_m2 = float(magnetic_field_t) / (
                    ELEMENTARY_CHARGE_C * float(hall_resistance_ohm)
                )
    return {
        "source_drain_excitation_v": None if excitation_v is None else float(excitation_v),
        "source_drain_nominal_current_a": nominal_current_a,
        "lockin_resistance_ohm": resistance_ohm,
        "lockin_conductance_s": conductance_s,
        "lockin_sheet_resistance_ohm_per_sq": sheet_resistance_ohm_per_sq,
        "lockin_sheet_conductivity_s_per_sq": sheet_conductivity_s_per_sq,
        "lockin_hall_resistance_ohm": hall_resistance_ohm,
        "lockin_hall_carrier_density_per_m2": hall_carrier_density_per_m2,
    }


def run_dual_gate_lockin_sweep(
    recipe: DualGateLockInRecipe,
    safety: SafetyPreset,
    gate1_smu: SourceMeasureUnit,
    gate2_smu: SourceMeasureUnit,
    lockin: LockInAmplifier,
    recipe_path: str | Path | None = None,
    progress_callback: Callable[[DualGateLockInPoint, int], None] | None = None,
    resume_from_run: str | Path | None = None,
) -> dict[str, Any]:
    validate_dual_gate_lockin_recipe_against_safety(recipe, safety)
    resume_state = (
        load_dual_gate_lockin_resume_state(resume_from_run, recipe) if resume_from_run is not None else None
    )
    resume_rows = list(resume_state.copied_rows) if resume_state is not None else None
    writer = DualGateLockInRunWriter(Path(recipe.output.directory), recipe.measurement_name, resume_rows=resume_rows)
    writer.write_yaml_snapshot(writer.recipe_snapshot_path, recipe.model_dump(mode="json"))
    writer.write_yaml_snapshot(writer.safety_snapshot_path, safety.model_dump(mode="json"))
    points_written = len(resume_rows or [])
    points_copied_from_resume = points_written
    points_measured_this_run = 0
    resume_last_row = (resume_rows or [None])[-1]
    gate1_config = build_voltage_source_config(recipe.gate1_instrument, recipe.gate1_sweep.current_compliance_a)
    gate2_config = build_voltage_source_config(recipe.gate2_instrument, recipe.gate2_sweep.current_compliance_a)
    gate1_voltages = gate_voltages_from_config(recipe.gate1_sweep)
    gate2_voltages = gate_voltages_from_config(recipe.gate2_sweep)
    total_points = len(gate1_voltages) * len(gate2_voltages)
    topology = recipe.topology.model_dump(mode="json")
    lockin_tc_s = lockin_time_constant_s(recipe.lockin)
    lockin_settle_s = lockin_read_settle_s(recipe.lockin)
    metadata: dict[str, Any] = {
        "measurement_name": recipe.measurement_name,
        "measurement_type": "dual_gate_lockin_sweep",
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "completed": False,
        "interrupted": False,
        "abort_class": None,
        "error_type": None,
        "error_message": None,
        "triggered_limit": None,
        "points_written": 0,
        "points_copied_from_resume": points_copied_from_resume,
        "points_measured_this_run": 0,
        "planned_points": total_points,
        "planned_gate_grid": planned_dual_gate_lockin_grid(recipe),
        "planned_gate_grid_signature": dual_gate_lockin_grid_signature(recipe),
        "planned_gate_grid_signature_algorithm": "sha256_json_v1",
        "remaining_points": max(0, total_points - points_written),
        "last_completed_index": int(resume_last_row["index"]) if resume_last_row is not None else None,
        "last_completed_gate1_index": int(resume_last_row["gate1_index"]) if resume_last_row is not None else None,
        "last_completed_gate2_index": int(resume_last_row["gate2_index"]) if resume_last_row is not None else None,
        "last_completed_gate1_voltage_v": (
            float(resume_last_row["gate1_voltage_v"]) if resume_last_row is not None else None
        ),
        "last_completed_gate2_voltage_v": (
            float(resume_last_row["gate2_voltage_v"]) if resume_last_row is not None else None
        ),
        "next_point_index": resume_state.next_point_index if resume_state is not None else 0,
        "resume_policy": (
            "contiguous_prefix_copy_then_continue" if resume_state is not None else "manual_resume_from_partial_run_supported"
        ),
        "resume_from_run": str(resume_state.source_run_dir) if resume_state is not None else None,
        "resume_source_metadata_path": str(resume_state.source_metadata_path) if resume_state is not None else None,
        "resume_source_csv_path": str(resume_state.source_csv_path) if resume_state is not None else None,
        "resume_source_points_written": resume_state.source_points_written if resume_state is not None else None,
        "resume_source_last_completed_index": (
            resume_state.source_last_completed_index if resume_state is not None else None
        ),
        "resume_next_point_index": resume_state.next_point_index if resume_state is not None else None,
        "recovery_recommendation": (
            "resume_in_progress_from_partial_run" if resume_state is not None else "run_not_completed_review_metadata_then_resume_or_restart"
        ),
        "gate_outputs_enabled": False,
        "outputs_off_after_run": False,
        "source_drain_transport_model": "lockin_r_v_divided_by_nominal_excitation_current",
        "sheet_transport_model": "longitudinal_resistance_times_width_over_length",
        "source_drain_excitation_v": recipe.topology.excitation_amplitude_v,
        "source_drain_nominal_current_a": nominal_source_drain_current_a(topology),
        "voltage_probe_role": recipe.topology.voltage_probe_role,
        "channel_length_m": recipe.topology.channel_length_m,
        "channel_width_m": recipe.topology.channel_width_m,
        "magnetic_field_t": recipe.topology.magnetic_field_t,
        "recipe": recipe.model_dump(mode="json"),
        "recipe_path": str(Path(recipe_path)) if recipe_path is not None else None,
        "safety": safety.model_dump(mode="json"),
        "run_dir": str(writer.run_dir),
        "gate1_instrument_probe": None,
        "gate2_instrument_probe": None,
        "lockin_probe": None,
        "lockin_settings_readback_available": None,
        "lockin_settings_readback_check": None,
        "lockin_settings_readback_matched": None,
        "lockin_settings_readback_enforced": False,
        "configured_gate1_smu": voltage_source_config_snapshot(gate1_config),
        "configured_gate2_smu": voltage_source_config_snapshot(gate2_config),
        "configured_gate1_smu_readback": None,
        "configured_gate2_smu_readback": None,
        "configured_gate1_smu_readback_check": None,
        "configured_gate2_smu_readback_check": None,
        "lockin_time_constant_s": lockin_tc_s,
        "lockin_settle_time_constants": recipe.lockin.settle_time_constants,
        "lockin_read_settle_s": lockin_settle_s,
        "csv_path": str(writer.csv_path),
        "metadata_path": str(writer.metadata_path),
        "recipe_snapshot_path": str(writer.recipe_snapshot_path),
        "safety_snapshot_path": str(writer.safety_snapshot_path),
    }
    initialize_output_state(metadata, ["gate1", "gate2"])

    try:
        gate1_smu.connect()
        gate2_smu.connect()
        lockin.connect()
        metadata["gate1_instrument_probe"] = gate1_smu.probe()
        metadata["gate2_instrument_probe"] = gate2_smu.probe()
        metadata["lockin_probe"] = lockin.probe()
        lockin_checks = compare_lockin_settings(recipe.lockin.model_dump(mode="json"), metadata["lockin_probe"])
        lockin_readback_available = lockin_settings_readback_available(metadata["lockin_probe"])
        metadata["lockin_settings_readback_available"] = lockin_readback_available
        metadata["lockin_settings_readback_check"] = lockin_setting_checks_to_dicts(lockin_checks)
        metadata["lockin_settings_readback_matched"] = (
            lockin_settings_ok(lockin_checks) if lockin_readback_available else None
        )
        metadata["lockin_settings_readback_enforced"] = lockin_readback_available
        raise_for_lockin_settings_mismatch(
            "lockin",
            lockin_checks,
            readback_available=lockin_readback_available,
        )
        gate1_smu.configure_voltage_source(gate1_config)
        gate2_smu.configure_voltage_source(gate2_config)
        metadata["configured_gate1_smu_readback"] = read_voltage_source_config_if_available(gate1_smu)
        metadata["configured_gate2_smu_readback"] = read_voltage_source_config_if_available(gate2_smu)
        metadata["configured_gate1_smu_readback_check"] = compare_voltage_source_config_readback(
            gate1_config, metadata["configured_gate1_smu_readback"]
        )
        metadata["configured_gate2_smu_readback_check"] = compare_voltage_source_config_readback(
            gate2_config, metadata["configured_gate2_smu_readback"]
        )
        raise_for_voltage_source_config_readback_mismatch("gate1", metadata["configured_gate1_smu_readback_check"])
        raise_for_voltage_source_config_readback_mismatch("gate2", metadata["configured_gate2_smu_readback_check"])
        output_on_with_state("gate1", gate1_smu, metadata)
        output_on_with_state("gate2", gate2_smu, metadata)
        metadata["gate_outputs_enabled"] = any_output_enabled(metadata)

        start = time.monotonic()
        point_index = 0
        for gate1_index, gate1_voltage_v in enumerate(gate1_voltages):
            gate1_row_end_index = point_index + len(gate2_voltages) - 1
            if resume_state is not None and resume_state.next_point_index > gate1_row_end_index:
                point_index += len(gate2_voltages)
                continue
            command_voltage_with_state("gate1", gate1_smu, metadata, float(gate1_voltage_v))
            if recipe.gate1_sweep.settle_s:
                time.sleep(recipe.gate1_sweep.settle_s)
            gate1_current_a, gate1_compliance_hit = gate1_smu.measure_current()
            if gate1_compliance_hit:
                raise SafetyLimitError("Gate1 instrument compliance was reached", "gate1_instrument_compliance")
            validate_point_current(gate1_current_a, safety)
            for gate2_index, gate2_voltage_v in enumerate(gate2_voltages):
                if resume_state is not None and point_index < resume_state.next_point_index:
                    point_index += 1
                    continue
                command_voltage_with_state("gate2", gate2_smu, metadata, float(gate2_voltage_v))
                if recipe.gate2_sweep.settle_s:
                    time.sleep(recipe.gate2_sweep.settle_s)
                gate2_current_a, gate2_compliance_hit = gate2_smu.measure_current()
                if gate2_compliance_hit:
                    raise SafetyLimitError("Gate2 instrument compliance was reached", "gate2_instrument_compliance")
                validate_point_current(gate2_current_a, safety)
                if lockin_settle_s:
                    time.sleep(lockin_settle_s)
                reading = lockin.read_channels()
                transport = derive_lockin_transport_values(
                    reading.r_v,
                    topology,
                )
                point = DualGateLockInPoint(
                    index=point_index,
                    gate1_index=gate1_index,
                    gate2_index=gate2_index,
                    gate1_voltage_v=float(gate1_voltage_v),
                    gate2_voltage_v=float(gate2_voltage_v),
                    gate1_current_a=float(gate1_current_a),
                    gate2_current_a=float(gate2_current_a),
                    elapsed_s=time.monotonic() - start,
                    gate1_compliance_hit=gate1_compliance_hit,
                    gate2_compliance_hit=gate2_compliance_hit,
                    lockin_x_v=reading.x_v,
                    lockin_y_v=reading.y_v,
                    lockin_r_v=reading.r_v,
                    lockin_theta_deg=reading.theta_deg,
                    source_drain_excitation_v=transport["source_drain_excitation_v"],
                    source_drain_nominal_current_a=transport["source_drain_nominal_current_a"],
                    lockin_resistance_ohm=transport["lockin_resistance_ohm"],
                    lockin_conductance_s=transport["lockin_conductance_s"],
                    lockin_sheet_resistance_ohm_per_sq=transport["lockin_sheet_resistance_ohm_per_sq"],
                    lockin_sheet_conductivity_s_per_sq=transport["lockin_sheet_conductivity_s_per_sq"],
                    lockin_hall_resistance_ohm=transport["lockin_hall_resistance_ohm"],
                    lockin_hall_carrier_density_per_m2=transport["lockin_hall_carrier_density_per_m2"],
                )
                writer.write_point(point)
                points_written += 1
                points_measured_this_run += 1
                metadata["last_completed_index"] = point.index
                metadata["last_completed_gate1_index"] = point.gate1_index
                metadata["last_completed_gate2_index"] = point.gate2_index
                metadata["last_completed_gate1_voltage_v"] = point.gate1_voltage_v
                metadata["last_completed_gate2_voltage_v"] = point.gate2_voltage_v
                point_index += 1
                if progress_callback is not None:
                    progress_callback(point, total_points)

        metadata["completed"] = True
        metadata["abort_class"] = "completed"
        metadata["recovery_recommendation"] = "run_completed_no_recovery_needed"
        return metadata
    except SafetyLimitError as exc:
        metadata["abort_class"] = "safety_stop"
        metadata["error_type"] = type(exc).__name__
        metadata["error_message"] = str(exc)
        metadata["triggered_limit"] = exc.triggered_limit
        metadata["recovery_recommendation"] = "do_not_resume_until_limit_cause_is_reviewed"
        return metadata
    except KeyboardInterrupt:
        metadata["interrupted"] = True
        metadata["abort_class"] = "interrupted"
        metadata["error_type"] = "KeyboardInterrupt"
        metadata["error_message"] = "Measurement interrupted by user"
        metadata["recovery_recommendation"] = "manual_review_required_restart_from_beginning_recommended"
        return metadata
    except Exception as exc:
        metadata["abort_class"] = "exception"
        metadata["error_type"] = type(exc).__name__
        metadata["error_message"] = str(exc)
        metadata["recovery_recommendation"] = "manual_review_required_before_restart"
        return metadata
    finally:
        zero_before_off_with_state("gate1", gate1_smu, metadata)
        zero_before_off_with_state("gate2", gate2_smu, metadata)
        output_off_with_state("gate1", gate1_smu, metadata)
        output_off_with_state("gate2", gate2_smu, metadata)
        metadata["gate_outputs_enabled"] = any_output_enabled(metadata)
        metadata["outputs_off_after_run"] = all_outputs_off_after_run(metadata, ["gate1", "gate2"])
        gate1_smu.close()
        gate2_smu.close()
        lockin.close()
        metadata["finished_at"] = datetime.now().isoformat(timespec="seconds")
        metadata["points_written"] = points_written
        metadata["points_measured_this_run"] = points_measured_this_run
        metadata["remaining_points"] = max(0, total_points - points_written)
        metadata["next_point_index"] = None if metadata["completed"] else points_written
        writer.write_metadata(metadata)
        writer.close()
