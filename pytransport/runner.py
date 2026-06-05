"""Drain I-V runner."""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from .errors import SafetyLimitError
from .instruments.base import SMUVoltageSourceConfig, SourceMeasureUnit
from .io import RunWriter
from .model import MeasurementPoint
from .recipes import DrainIVRecipe, SafetyPreset, sweep_delays, sweep_voltages
from .safety import validate_point_current, validate_recipe_against_safety


def run_drain_iv(
    recipe: DrainIVRecipe,
    safety: SafetyPreset,
    smu: SourceMeasureUnit,
    recipe_path: str | Path | None = None,
    progress_callback: Callable[[MeasurementPoint, int], None] | None = None,
    stop_requested: Callable[[], bool] | None = None,
) -> dict[str, Any]:
    validate_recipe_against_safety(recipe, safety)
    writer = RunWriter(Path(recipe.output.directory), recipe.measurement_name)
    writer.write_yaml_snapshot(writer.recipe_snapshot_path, recipe.model_dump(mode="json"))
    writer.write_yaml_snapshot(writer.safety_snapshot_path, safety.model_dump(mode="json"))
    points_written = 0
    metadata: dict[str, Any] = {
        "measurement_name": recipe.measurement_name,
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "completed": False,
        "interrupted": False,
        "error_type": None,
        "error_message": None,
        "triggered_limit": None,
        "points_written": 0,
        "recipe": recipe.model_dump(mode="json"),
        "recipe_path": str(Path(recipe_path)) if recipe_path is not None else None,
        "safety": safety.model_dump(mode="json"),
        "run_dir": str(writer.run_dir),
        "instrument_idn": None,
        "instrument_probe": None,
        "current_limit_command": None,
        "csv_path": str(writer.csv_path),
        "metadata_path": str(writer.metadata_path),
        "recipe_snapshot_path": str(writer.recipe_snapshot_path),
        "safety_snapshot_path": str(writer.safety_snapshot_path),
        "plot_path": None,
        "report_path": None,
    }

    try:
        smu.connect()
        probe = smu.probe()
        metadata["instrument_probe"] = probe
        metadata["instrument_idn"] = probe.get("idn")
        smu.configure_voltage_source(
            SMUVoltageSourceConfig(
                current_compliance_a=recipe.sweep.current_compliance_a,
                voltage_range_v=recipe.instrument.voltage_range_v,
                current_range_a=recipe.instrument.current_range_a,
                terminal=recipe.instrument.terminal,
            )
        )
        metadata["current_limit_command"] = getattr(smu, "current_limit_command", None)
        smu.output_on()

        start = time.monotonic()
        voltages = sweep_voltages(recipe.sweep)
        delays = sweep_delays(recipe.sweep)
        for index, (voltage_v, delay_s) in enumerate(zip(voltages, delays)):
            raise_if_stop_requested(stop_requested)
            smu.set_voltage(float(voltage_v))
            sleep_with_stop_check(delay_s, stop_requested)
            raise_if_stop_requested(stop_requested)
            current_a, compliance_hit = smu.measure_current()
            if compliance_hit:
                raise SafetyLimitError("Instrument compliance was reached", "instrument_compliance")
            validate_point_current(current_a, safety)
            resistance_ohm = None if current_a == 0 else float(voltage_v) / current_a
            point = MeasurementPoint(
                index=index,
                voltage_v=float(voltage_v),
                current_a=float(current_a),
                elapsed_s=time.monotonic() - start,
                resistance_ohm=resistance_ohm,
                compliance_hit=compliance_hit,
            )
            writer.write_point(point)
            points_written += 1
            if progress_callback is not None:
                progress_callback(point, len(voltages))

        metadata["completed"] = True
        return metadata
    except SafetyLimitError as exc:
        metadata["error_type"] = type(exc).__name__
        metadata["error_message"] = str(exc)
        metadata["triggered_limit"] = exc.triggered_limit
        return metadata
    except KeyboardInterrupt as exc:
        metadata["interrupted"] = True
        metadata["error_type"] = type(exc).__name__
        metadata["error_message"] = "Measurement interrupted by user"
        return metadata
    except Exception as exc:
        metadata["error_type"] = type(exc).__name__
        metadata["error_message"] = str(exc)
        return metadata
    finally:
        try:
            smu.output_off()
        finally:
            smu.close()
            metadata["finished_at"] = datetime.now().isoformat(timespec="seconds")
            metadata["points_written"] = points_written
            writer.write_metadata(metadata)
            writer.close()


def raise_if_stop_requested(stop_requested: Callable[[], bool] | None) -> None:
    if stop_requested is not None and stop_requested():
        raise KeyboardInterrupt()


def sleep_with_stop_check(delay_s: float, stop_requested: Callable[[], bool] | None) -> None:
    remaining = float(delay_s or 0)
    while remaining > 0:
        raise_if_stop_requested(stop_requested)
        interval = min(remaining, 0.05)
        time.sleep(interval)
        remaining -= interval
