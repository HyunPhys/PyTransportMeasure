"""Hardware-facing measurement mode execution matrix."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal


ModeStatus = Literal["hardware_verified", "hardware_smoke_ready", "dry_run_ready", "planned"]


@dataclass(frozen=True)
class MeasurementMode:
    key: str
    label: str
    status: ModeStatus
    measurement_type: str
    geometry: str
    primary_instruments: tuple[str, ...]
    recipe_examples: tuple[str, ...]
    plan_commands: tuple[str, ...]
    preflight_commands: tuple[str, ...]
    run_commands: tuple[str, ...]
    guarded_parameters: tuple[str, ...]
    safety_gates: tuple[str, ...]
    current_limitations: tuple[str, ...]
    next_step: str

    def to_dict(self) -> dict:
        return asdict(self)


MEASUREMENT_MODES: tuple[MeasurementMode, ...] = (
    MeasurementMode(
        key="two_terminal_dc",
        label="Two-terminal DC I-V",
        status="hardware_verified",
        measurement_type="drain_iv",
        geometry="two_terminal, 2-terminal",
        primary_instruments=("Keithley 2450 source/measure",),
        recipe_examples=(
            "configs/recipes/drain_iv_1k_resistor.yaml",
            "configs/recipes/drain_iv_nanodevice_safe.yaml",
        ),
        plan_commands=("ptm plan configs/recipes/drain_iv_1k_resistor.yaml",),
        preflight_commands=("ptm preflight configs/recipes/drain_iv_1k_resistor.yaml",),
        run_commands=(
            "ptm run configs/recipes/drain_iv_1k_resistor.yaml --progress --summary --plot --report",
        ),
        guarded_parameters=(
            "Keithley address",
            "terminal",
            "voltage_range_v",
            "current_range_a",
            "nplc",
            "source_delay_s",
            "current_compliance_a",
            "safety preset",
        ),
        safety_gates=(
            "recipe safety validation",
            "Keithley parameter audit",
            "readback mismatch stops before acquisition",
            "output off in finally path",
        ),
        current_limitations=("Keithley remote-sense/four-probe DC is still planned",),
        next_step="Keep as baseline smoke test before multi-instrument runs.",
    ),
    MeasurementMode(
        key="four_terminal_dc",
        label="Four-terminal DC",
        status="hardware_smoke_ready",
        measurement_type="dc_four_terminal",
        geometry="four_terminal, 4-terminal",
        primary_instruments=("Keithley 2450 source", "Keithley 2450 voltage-sense or sense terminals"),
        recipe_examples=("configs/recipes/four_terminal_dc_schema_draft.yaml",),
        plan_commands=(),
        preflight_commands=(
            "ptm four-terminal-dc-preflight configs/recipes/four_terminal_dc_schema_draft.yaml --dry-check",
            "ptm four-terminal-dc-preflight configs/recipes/four_terminal_dc_schema_draft.yaml",
            "ptm four-terminal-dc-command-review configs/recipes/four_terminal_dc_schema_draft.yaml --preflight-json docs/four_terminal_dc_preflight.json --dry-run-metadata data/raw/<run>/metadata.json",
        ),
        run_commands=(
            "ptm four-terminal-dc configs/recipes/four_terminal_dc_schema_draft.yaml --dry-run --fake-resistance-ohm 1000000 --progress",
            "ptm four-terminal-dc configs/recipes/four_terminal_dc_schema_draft.yaml --allow-active-run --command-review-json docs/four_terminal_dc_command_review.json --hardware-approval-note \"fixture contacts checked; preflight passed\" --max-hardware-points 3 --yes --progress",
        ),
        guarded_parameters=(
            "source Keithley NPLC/range/compliance",
            "sense terminal mode",
            "force/sense contact map",
            "contact overlap guard",
        ),
        safety_gates=(
            "do not enable output until 4-probe contact topology validates",
            "read :SENS:CURR:RSEN? before any future output path",
            "keep active hardware run disabled while preflight is being verified",
        ),
        current_limitations=("Guarded active runner draft exists; first lab smoke feedback is still required.",),
        next_step="Run the guarded four-terminal DC lab smoke and ingest returned metadata before broadening.",
    ),
    MeasurementMode(
        key="two_terminal_ac",
        label="Two-terminal AC lock-in",
        status="hardware_smoke_ready",
        measurement_type="ac_lockin_sweep",
        geometry="two_terminal, 2-terminal",
        primary_instruments=("Keithley 2450 source bias", "SRS SR860 lock-in"),
        recipe_examples=(
            "configs/recipes/ac_lockin_dry_run.yaml",
            "configs/recipes/ac_lockin_hardware_smoke.yaml",
        ),
        plan_commands=("ptm ac-lockin-plan configs/recipes/ac_lockin_hardware_smoke.yaml",),
        preflight_commands=("ptm ac-lockin-preflight configs/recipes/ac_lockin_hardware_smoke.yaml",),
        run_commands=(
            "ptm ac-lockin configs/recipes/ac_lockin_hardware_smoke.yaml --progress --summary --plot --report",
            "ptm ac-lockin-lab-smoke-intake data/raw/<run> --min-points 5 --min-abs-lockin-r-v <low> --max-abs-lockin-r-v <high>",
        ),
        guarded_parameters=(
            "Keithley voltage_range_v",
            "Keithley current_range_a",
            "Keithley nplc",
            "source current compliance",
            "SR860 sensitivity index",
            "SR860 time constant index",
            "lock-in read settle",
        ),
        safety_gates=(
            "AC preflight probes Keithley and SR860",
            "SR860 readback mismatch blocks hardware run when readback is available",
            "post-run intake requires source SMU readback, SR860 readback, output cleanup, and lock-in signal window",
            "Keithley output off in finally path",
        ),
        current_limitations=("Requires lab hardware confirmation for actual AC wiring/noise floor.",),
        next_step="Run lab smoke with known resistor/current-bias wiring, then pass ac-lockin-lab-smoke-intake before broadening.",
    ),
    MeasurementMode(
        key="four_terminal_ac",
        label="Four-terminal AC lock-in",
        status="dry_run_ready",
        measurement_type="ac_lockin_sweep",
        geometry="four_terminal, 4-terminal",
        primary_instruments=("Keithley 2450 source bias", "SRS SR860 differential voltage input"),
        recipe_examples=("configs/recipes/ac_lockin_four_terminal_dry_run.yaml",),
        plan_commands=("ptm ac-lockin-plan configs/recipes/ac_lockin_four_terminal_dry_run.yaml",),
        preflight_commands=("ptm ac-lockin-preflight configs/recipes/ac_lockin_four_terminal_dry_run.yaml",),
        run_commands=(
            "ptm ac-lockin configs/recipes/ac_lockin_four_terminal_dry_run.yaml --dry-run --summary --plot --report",
        ),
        guarded_parameters=(
            "four-terminal contact map",
            "voltage contact pair",
            "SR860 voltage input mode",
            "input coupling",
            "shield grounding notes",
        ),
        safety_gates=(
            "contact overlap validation",
            "four-terminal lock-in recipes require voltage readout topology",
        ),
        current_limitations=("Dry-run and recipe guard exist; hardware execution needs lab smoke validation.",),
        next_step="Promote to hardware-smoke-ready after SR860 differential voltage wiring test.",
    ),
    MeasurementMode(
        key="hall_dual_gate_lockin",
        label="Hall-bar dual-gate lock-in suite",
        status="dry_run_ready",
        measurement_type="dual_gate_lockin_sweep",
        geometry="four_terminal Hall-bar, dual-gate",
        primary_instruments=("Keithley 2450 gate1", "Keithley 2450 gate2", "SRS SR860"),
        recipe_examples=(
            "configs/recipes/dual_gate_lockin_four_terminal_dry_run.yaml",
            "configs/recipes/dual_gate_lockin_hall_dry_run.yaml",
        ),
        plan_commands=(
            "ptm dual-gate-lockin-hall-suite-template configs/recipes/dual_gate_lockin_four_terminal_dry_run.yaml configs/recipes/<suite> --measurement-prefix <prefix> --magnetic-field-t <B>",
            "ptm dual-gate-lockin-hall-suite-package configs/recipes/<suite>/<prefix>_vxx.yaml configs/recipes/<suite>/<prefix>_vxy_plus_b.yaml configs/recipes/<suite>/<prefix>_vxy_minus_b.yaml data/hall_packages --zero-field-recipe configs/recipes/<suite>/<prefix>_vxy_zero_b.yaml --package-name <package>",
        ),
        preflight_commands=(
            "ptm dual-gate-lockin-preflight configs/recipes/<suite>/<prefix>_vxx.yaml",
            "ptm dual-gate-lockin-hall-suite-lifecycle-status data/hall_packages/<package>",
        ),
        run_commands=(
            "ptm dual-gate-lockin configs/recipes/<suite>/<prefix>_vxx.yaml --allow-active-sweep --max-hardware-points <N> --progress --plot --report --gate-stats",
        ),
        guarded_parameters=(
            "gate1/gate2 address separation",
            "gate1/gate2 NPLC",
            "gate voltage/current ranges",
            "gate current compliance",
            "gate settle time",
            "SR860 sensitivity/time constant/read settle",
            "Vxx/Vxy contact geometry",
            "magnetic_field_t",
        ),
        safety_gates=(
            "chunked active sweep point guard",
            "Keithley parameter audit",
            "SR860 setting audit",
            "condition snapshot and drift audits before analysis",
            "return bundle lifecycle archive after analysis",
        ),
        current_limitations=("Dry-run/package workflow exists; full graphene Hall hardware run awaits lab feedback.",),
        next_step="Use this as the main development path toward Hall-bar graphene dual-gate scans.",
    ),
)


def measurement_mode_matrix() -> tuple[MeasurementMode, ...]:
    return MEASUREMENT_MODES


def measurement_mode_by_key(key: str) -> MeasurementMode:
    for mode in MEASUREMENT_MODES:
        if mode.key == key:
            return mode
    known = ", ".join(mode.key for mode in MEASUREMENT_MODES)
    raise ValueError(f"Unknown measurement mode {key!r}; known modes: {known}")


def measurement_mode_matrix_payload() -> dict:
    return {
        "schema": "pytransport.measurement_modes.v1",
        "mode_count": len(MEASUREMENT_MODES),
        "modes": [mode.to_dict() for mode in MEASUREMENT_MODES],
    }


def write_measurement_mode_matrix_json(output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(measurement_mode_matrix_payload(), indent=2, sort_keys=True), encoding="utf-8")
    return path


def format_measurement_mode_matrix(*, verbose: bool = False) -> str:
    lines = [
        "PyTransportMeasure Measurement Mode Execution Matrix",
        "",
        "| Key | Status | Measurement type | Geometry | Instruments | Next step |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for mode in MEASUREMENT_MODES:
        lines.append(
            (
                f"| {mode.key} | {mode.status} | {mode.measurement_type} | {mode.geometry} | "
                f"{', '.join(mode.primary_instruments)} | {mode.next_step} |"
            )
        )
    if not verbose:
        return "\n".join(lines)

    for mode in MEASUREMENT_MODES:
        lines.extend(
            [
                "",
                f"## {mode.label}",
                "",
                f"- Key: `{mode.key}`",
                f"- Status: {mode.status}",
                f"- Measurement type: `{mode.measurement_type}`",
                f"- Geometry: {mode.geometry}",
                f"- Instruments: {', '.join(mode.primary_instruments)}",
                f"- Recipe examples: {_format_tuple(mode.recipe_examples)}",
                f"- Guarded parameters: {_format_tuple(mode.guarded_parameters)}",
                f"- Safety gates: {_format_tuple(mode.safety_gates)}",
                f"- Current limitations: {_format_tuple(mode.current_limitations)}",
                f"- Next step: {mode.next_step}",
            ]
        )
        if mode.plan_commands:
            lines.extend(["", "Plan/package commands:", "", "```powershell", *mode.plan_commands, "```"])
        if mode.preflight_commands:
            lines.extend(["", "Preflight/status commands:", "", "```powershell", *mode.preflight_commands, "```"])
        if mode.run_commands:
            lines.extend(["", "Run commands:", "", "```powershell", *mode.run_commands, "```"])
    return "\n".join(lines)


def _format_tuple(values: tuple[str, ...]) -> str:
    return ", ".join(values) if values else "not implemented yet"
