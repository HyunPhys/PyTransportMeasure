"""Command-line interface for PyTransportMeasure."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Callable

from .batch import (
    create_batch_summary,
    finish_batch_summary,
    format_batch_plan,
    load_batch,
    resolve_batch_entries,
)
from .ac_lockin import run_ac_lockin_sweep
from .ac_lockin_review import write_ac_lockin_plot_svg, write_ac_lockin_report
from .batch_review import (
    evaluate_batch_quality,
    format_batch_quality,
    format_batch_review,
    summarize_batch,
    update_batch_summary_quality,
    write_batch_overlay_svg,
    write_batch_points_csv,
    write_batch_report,
    write_batch_runs_csv,
    write_batch_stats_csv,
)
from .campaign import (
    CampaignFilters,
    create_campaign,
    export_campaign_bundle,
    write_campaign_report as write_campaign_review_report,
    write_campaign_resistance_histogram_svg,
    write_campaign_stats_csv,
)
from .doctor import doctor_report_to_dict, format_doctor_report, run_doctor, write_doctor_report
from .dual_gate import run_dual_gate_sweep
from .dual_gate_review import (
    format_dual_gate_summary,
    summarize_dual_gate_run,
    write_dual_gate_heatmap_svg,
    write_dual_gate_report,
    write_dual_gate_stats_csv,
)
from .dual_gate_lockin import dual_gate_lockin_point_count, run_dual_gate_lockin_sweep
from .dual_gate_lockin_smoke import (
    format_dual_gate_lockin_active_smoke_plan,
    format_dual_gate_lockin_smoke_plan,
    run_dual_gate_lockin_active_gate_smoke,
    run_dual_gate_lockin_readout_smoke,
)
from .dual_gate_lockin_review import (
    format_dual_gate_lockin_summary,
    summarize_dual_gate_lockin_run,
    write_dual_gate_lockin_heatmap_svg,
    write_dual_gate_lockin_report,
    write_dual_gate_lockin_stats_csv,
)
from .feedback_bundle import create_feedback_bundle
from .inspect import inspect_run
from .instruments.fake import (
    CoupledFakeDeviceState,
    CoupledFakeSMU,
    DualGateFakeDeviceState,
    DualGateFakeLockIn,
    DualGateFakeSMU,
    FakeLockIn,
    FakeSMU,
)
from .instruments.keithley_2450 import Keithley2450
from .instruments.srs_sr860 import SRS_SR860, probe_srs_sr860
from .method_registry import handler_for_measurement_type, handler_for_metadata, known_measurement_types
from .model import MeasurementPoint
from .plot import write_iv_svg
from .preflight import (
    format_ac_lockin_preflight_report,
    format_dual_gate_lockin_preflight_report,
    format_preflight_report,
    format_single_gate_preflight_report,
    run_ac_lockin_preflight,
    run_dual_gate_lockin_preflight,
    run_preflight,
    run_preflight_for_recipe,
    run_single_gate_preflight,
    run_single_gate_preflight_for_recipe,
)
from .pulse import run_pulse_measurement
from .pulse_review import write_pulse_plot_svg, write_pulse_report
from .quality import evaluate_run_quality, format_quality_report, quality_report_to_dict
from .recipes import load_named_safety_preset, load_recipe
from .report import write_run_report
from .run_index import append_run_index, filter_run_index, format_run_index, read_run_index, rebuild_run_index
from .runner import run_drain_iv
from .safety import (
    validate_ac_lockin_recipe_against_safety,
    validate_dual_gate_lockin_recipe_against_safety,
    validate_dual_gate_recipe_against_safety,
    validate_pulse_recipe_against_safety,
    validate_single_gate_recipe_against_safety,
)
from .scheme import (
    create_scheme_summary,
    finish_scheme_summary,
    format_scheme_plan,
    load_scheme,
    load_scheme_step_recipe,
    load_scheme_step_single_gate_recipe,
    resolve_scheme_steps,
)
from .scheme_review import (
    evaluate_scheme_quality,
    format_scheme_quality,
    update_scheme_summary_quality,
    write_scheme_overlay_svg,
    write_scheme_points_csv,
    write_scheme_report as write_scheme_review_report,
    write_scheme_runs_csv,
    write_scheme_stats_csv,
)
from .summary import format_summary, summarize_run
from .single_gate import run_single_gate_sweep
from .single_gate_review import (
    format_single_gate_summary,
    summarize_single_gate_run,
    write_single_gate_heatmap_svg,
    write_single_gate_report,
    write_single_gate_stats_csv,
)
from .templates import write_batch_template, write_recipe_template
from .templates import write_scheme_template
from .validation import format_validation_report, validate_recipe_file
from .visa_utils import list_resources


def update_metadata_file(metadata_path: Path, updates: dict[str, str | None]) -> None:
    with metadata_path.open("r", encoding="utf-8") as handle:
        metadata = json.load(handle)
    metadata.update(updates)
    with metadata_path.open("w", encoding="utf-8") as handle:
        json.dump(metadata, handle, indent=2, sort_keys=True, default=str)


def read_metadata_file(metadata_path: Path) -> dict:
    with metadata_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{metadata_path} must contain a JSON object")
    return data


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ptm")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list-resources", help="List VISA resources visible to PyVISA.")

    doctor = subparsers.add_parser("doctor", help="Print lab laptop environment and VISA diagnostics.")
    doctor.add_argument("--instrument", default="keithley_2450", choices=["keithley_2450", "srs_sr860"])
    doctor.add_argument("--address", help="Optional VISA address to check and probe.")
    doctor.add_argument("--timeout-ms", type=int, default=10000)
    doctor.add_argument("--json", action="store_true", help="Print JSON instead of text.")
    doctor.add_argument("--output", type=Path, help="Write the report to a file.")

    identify = subparsers.add_parser("identify", help="Query *IDN? for a supported instrument.")
    identify.add_argument("--instrument", default="keithley_2450", choices=["keithley_2450", "srs_sr860"])
    identify.add_argument("--address", required=True)
    identify.add_argument("--timeout-ms", type=int, default=10000)

    probe = subparsers.add_parser("probe", help="Probe a supported instrument with conservative read-only queries.")
    probe.add_argument("--instrument", default="keithley_2450", choices=["keithley_2450", "srs_sr860"])
    probe.add_argument("--address", required=True)
    probe.add_argument("--timeout-ms", type=int, default=10000)

    run = subparsers.add_parser("run", help="Run a Drain I-V recipe.")
    run.add_argument("recipe", type=Path)
    run.add_argument("--dry-run", action="store_true")
    run.add_argument("--fake-resistance-ohm", type=float, default=10_000_000.0)
    run.add_argument("--fake-noise-std-a", type=float, default=1e-10)
    run.add_argument("--safety-dir", type=Path, default=Path("configs/safety"))
    run.add_argument("--summary", action="store_true", help="Print a run summary after measurement.")
    run.add_argument("--plot", action="store_true", help="Write iv_plot.svg after measurement.")
    run.add_argument("--report", action="store_true", help="Write report.md after measurement.")
    run.add_argument("--progress", action="store_true", help="Print each measured point while running.")
    run.add_argument("--index-path", type=Path, default=Path("data/run_index.jsonl"))
    run.add_argument("--yes", action="store_true", help="Skip the interactive hardware confirmation prompt.")
    run.add_argument("--preview-points", type=int, default=5, help="Number of leading/trailing planned points to show.")

    single_gate_plan = subparsers.add_parser("single-gate-plan", help="Show a single-gate sweep plan without hardware.")
    single_gate_plan.add_argument("recipe", type=Path)
    single_gate_plan.add_argument("--safety-dir", type=Path, default=Path("configs/safety"))
    single_gate_plan.add_argument("--preview-points", type=int, default=5)

    single_gate_preflight = subparsers.add_parser(
        "single-gate-preflight",
        help="Validate a single-gate recipe, find both VISA addresses, and probe both Keithleys.",
    )
    single_gate_preflight.add_argument("recipe", type=Path)
    single_gate_preflight.add_argument("--safety-dir", type=Path, default=Path("configs/safety"))

    single_gate = subparsers.add_parser("single-gate", help="Run a single-gate sweep recipe.")
    single_gate.add_argument("recipe", type=Path)
    single_gate.add_argument("--dry-run", action="store_true")
    single_gate.add_argument("--fake-channel-resistance-ohm", type=float, default=1_000_000.0)
    single_gate.add_argument("--fake-gate-leak-resistance-ohm", type=float, default=1_000_000_000.0)
    single_gate.add_argument("--fake-gate-modulation-per-v", type=float, default=0.0)
    single_gate.add_argument("--fake-noise-std-a", type=float, default=1e-10)
    single_gate.add_argument("--safety-dir", type=Path, default=Path("configs/safety"))
    single_gate.add_argument("--summary", action="store_true", help="Print a single-gate summary after measurement.")
    single_gate.add_argument("--plot", action="store_true", help="Write single_gate_heatmap.svg after measurement.")
    single_gate.add_argument("--report", action="store_true", help="Write single_gate_report.md after measurement.")
    single_gate.add_argument("--gate-stats", action="store_true", help="Write single_gate_stats.csv after measurement.")
    single_gate.add_argument("--progress", action="store_true")
    single_gate.add_argument("--index-path", type=Path, default=Path("data/run_index.jsonl"))
    single_gate.add_argument("--yes", action="store_true", help="Skip the interactive hardware confirmation prompt.")
    single_gate.add_argument("--preview-points", type=int, default=5)

    dual_gate_plan = subparsers.add_parser("dual-gate-plan", help="Show a dual-gate sweep plan without hardware.")
    dual_gate_plan.add_argument("recipe", type=Path)
    dual_gate_plan.add_argument("--safety-dir", type=Path, default=Path("configs/safety"))
    dual_gate_plan.add_argument("--preview-points", type=int, default=5)

    dual_gate = subparsers.add_parser("dual-gate", help="Run a dual-gate sweep recipe. Current milestone is dry-run only.")
    dual_gate.add_argument("recipe", type=Path)
    dual_gate.add_argument("--dry-run", action="store_true")
    dual_gate.add_argument("--fake-channel-resistance-ohm", type=float, default=1_000_000.0)
    dual_gate.add_argument("--fake-gate1-leak-resistance-ohm", type=float, default=1_000_000_000.0)
    dual_gate.add_argument("--fake-gate2-leak-resistance-ohm", type=float, default=1_000_000_000.0)
    dual_gate.add_argument("--fake-gate1-modulation-per-v", type=float, default=0.0)
    dual_gate.add_argument("--fake-gate2-modulation-per-v", type=float, default=0.0)
    dual_gate.add_argument("--fake-cross-term-per-v2", type=float, default=0.0)
    dual_gate.add_argument("--fake-noise-std-a", type=float, default=1e-10)
    dual_gate.add_argument("--safety-dir", type=Path, default=Path("configs/safety"))
    dual_gate.add_argument("--summary", action="store_true", help="Print a dual-gate summary after measurement.")
    dual_gate.add_argument("--plot", action="store_true", help="Write dual_gate_heatmap.svg after measurement.")
    dual_gate.add_argument("--report", action="store_true", help="Write dual_gate_report.md after measurement.")
    dual_gate.add_argument("--gate-stats", action="store_true", help="Write dual_gate_stats.csv after measurement.")
    dual_gate.add_argument("--progress", action="store_true")
    dual_gate.add_argument("--index-path", type=Path, default=Path("data/run_index.jsonl"))
    dual_gate.add_argument("--preview-points", type=int, default=5)

    dual_gate_lockin_plan = subparsers.add_parser("dual-gate-lockin-plan", help="Show a dual-gate lock-in sweep plan without hardware.")
    dual_gate_lockin_plan.add_argument("recipe", type=Path)
    dual_gate_lockin_plan.add_argument("--safety-dir", type=Path, default=Path("configs/safety"))
    dual_gate_lockin_plan.add_argument("--preview-points", type=int, default=5)

    dual_gate_lockin_preflight = subparsers.add_parser(
        "dual-gate-lockin-preflight",
        help="Validate a dual-gate lock-in recipe, find two gate Keithleys and SR860, and probe all three instruments.",
    )
    dual_gate_lockin_preflight.add_argument("recipe", type=Path)
    dual_gate_lockin_preflight.add_argument("--safety-dir", type=Path, default=Path("configs/safety"))

    dual_gate_lockin_smoke = subparsers.add_parser(
        "dual-gate-lockin-smoke",
        help="Read SR860 lock-in channels for a dual-gate lock-in topology without enabling gate outputs.",
    )
    dual_gate_lockin_smoke.add_argument("recipe", type=Path)
    dual_gate_lockin_smoke.add_argument("--dry-run", action="store_true")
    dual_gate_lockin_smoke.add_argument("--samples", type=int, default=5)
    dual_gate_lockin_smoke.add_argument("--interval-s", type=float, default=0.2)
    dual_gate_lockin_smoke.add_argument("--fake-lockin-r-v", type=float, default=1e-6)
    dual_gate_lockin_smoke.add_argument("--fake-lockin-phase-deg", type=float, default=0.0)
    dual_gate_lockin_smoke.add_argument("--fake-noise-std", type=float, default=0.0)
    dual_gate_lockin_smoke.add_argument("--safety-dir", type=Path, default=Path("configs/safety"))
    dual_gate_lockin_smoke.add_argument("--progress", action="store_true")
    dual_gate_lockin_smoke.add_argument("--index-path", type=Path, default=Path("data/run_index.jsonl"))

    dual_gate_lockin_active_smoke = subparsers.add_parser(
        "dual-gate-lockin-active-smoke",
        help="Apply one safe gate-bias point, read leakage and SR860 channels, then turn gate outputs off.",
    )
    dual_gate_lockin_active_smoke.add_argument("recipe", type=Path)
    dual_gate_lockin_active_smoke.add_argument("--dry-run", action="store_true")
    dual_gate_lockin_active_smoke.add_argument("--gate1-v", type=float, required=True)
    dual_gate_lockin_active_smoke.add_argument("--gate2-v", type=float, required=True)
    dual_gate_lockin_active_smoke.add_argument("--settle-s", type=float, default=0.2)
    dual_gate_lockin_active_smoke.add_argument("--samples", type=int, default=3)
    dual_gate_lockin_active_smoke.add_argument("--interval-s", type=float, default=0.2)
    dual_gate_lockin_active_smoke.add_argument("--fake-gate1-leak-resistance-ohm", type=float, default=1_000_000_000.0)
    dual_gate_lockin_active_smoke.add_argument("--fake-gate2-leak-resistance-ohm", type=float, default=1_000_000_000.0)
    dual_gate_lockin_active_smoke.add_argument("--fake-lockin-r-v", type=float, default=1e-6)
    dual_gate_lockin_active_smoke.add_argument("--fake-lockin-phase-deg", type=float, default=0.0)
    dual_gate_lockin_active_smoke.add_argument("--fake-noise-std", type=float, default=0.0)
    dual_gate_lockin_active_smoke.add_argument("--safety-dir", type=Path, default=Path("configs/safety"))
    dual_gate_lockin_active_smoke.add_argument("--progress", action="store_true")
    dual_gate_lockin_active_smoke.add_argument("--index-path", type=Path, default=Path("data/run_index.jsonl"))
    dual_gate_lockin_active_smoke.add_argument("--yes", action="store_true", help="Skip the interactive hardware confirmation prompt.")

    dual_gate_lockin = subparsers.add_parser("dual-gate-lockin", help="Run a dual-gate lock-in recipe. Current milestone is dry-run only.")
    dual_gate_lockin.add_argument("recipe", type=Path)
    dual_gate_lockin.add_argument("--dry-run", action="store_true")
    dual_gate_lockin.add_argument("--fake-gate1-leak-resistance-ohm", type=float, default=1_000_000_000.0)
    dual_gate_lockin.add_argument("--fake-gate2-leak-resistance-ohm", type=float, default=1_000_000_000.0)
    dual_gate_lockin.add_argument("--fake-lockin-r-v", type=float, default=1e-6)
    dual_gate_lockin.add_argument("--fake-lockin-gate1-sensitivity-v-per-v", type=float, default=0.0)
    dual_gate_lockin.add_argument("--fake-lockin-gate2-sensitivity-v-per-v", type=float, default=0.0)
    dual_gate_lockin.add_argument("--fake-lockin-cross-sensitivity-v-per-v2", type=float, default=0.0)
    dual_gate_lockin.add_argument("--fake-lockin-phase-deg", type=float, default=0.0)
    dual_gate_lockin.add_argument("--fake-noise-std", type=float, default=0.0)
    dual_gate_lockin.add_argument("--safety-dir", type=Path, default=Path("configs/safety"))
    dual_gate_lockin.add_argument("--summary", action="store_true")
    dual_gate_lockin.add_argument("--plot", action="store_true")
    dual_gate_lockin.add_argument("--report", action="store_true")
    dual_gate_lockin.add_argument("--gate-stats", action="store_true")
    dual_gate_lockin.add_argument("--progress", action="store_true")
    dual_gate_lockin.add_argument("--index-path", type=Path, default=Path("data/run_index.jsonl"))
    dual_gate_lockin.add_argument("--preview-points", type=int, default=5)
    dual_gate_lockin.add_argument("--allow-active-sweep", action="store_true", help="Enable the guarded hardware gate sweep path.")
    dual_gate_lockin.add_argument("--max-hardware-points", type=int, default=9, help="Maximum allowed hardware points for guarded active sweep.")
    dual_gate_lockin.add_argument("--yes", action="store_true", help="Skip the interactive hardware confirmation prompt.")

    ac_lockin_plan = subparsers.add_parser("ac-lockin-plan", help="Show an AC/lock-in bias sweep plan without hardware.")
    ac_lockin_plan.add_argument("recipe", type=Path)
    ac_lockin_plan.add_argument("--safety-dir", type=Path, default=Path("configs/safety"))
    ac_lockin_plan.add_argument("--preview-points", type=int, default=5)

    ac_lockin_preflight = subparsers.add_parser(
        "ac-lockin-preflight",
        help="Validate an AC/lock-in recipe, find source and SR860 addresses, and probe both instruments.",
    )
    ac_lockin_preflight.add_argument("recipe", type=Path)
    ac_lockin_preflight.add_argument("--safety-dir", type=Path, default=Path("configs/safety"))

    ac_lockin = subparsers.add_parser("ac-lockin", help="Run an AC/lock-in bias sweep recipe.")
    ac_lockin.add_argument("recipe", type=Path)
    ac_lockin.add_argument("--dry-run", action="store_true")
    ac_lockin.add_argument("--fake-resistance-ohm", type=float, default=1_000_000.0)
    ac_lockin.add_argument("--fake-lockin-r-v", type=float, default=1e-6)
    ac_lockin.add_argument("--fake-lockin-phase-deg", type=float, default=0.0)
    ac_lockin.add_argument("--fake-noise-std", type=float, default=0.0)
    ac_lockin.add_argument("--safety-dir", type=Path, default=Path("configs/safety"))
    ac_lockin.add_argument("--summary", action="store_true")
    ac_lockin.add_argument("--plot", action="store_true")
    ac_lockin.add_argument("--report", action="store_true")
    ac_lockin.add_argument("--progress", action="store_true")
    ac_lockin.add_argument("--index-path", type=Path, default=Path("data/run_index.jsonl"))
    ac_lockin.add_argument("--preview-points", type=int, default=5)
    ac_lockin.add_argument("--yes", action="store_true", help="Skip the interactive hardware confirmation prompt.")

    pulse_plan = subparsers.add_parser("pulse-plan", help="Show a pulse measurement plan without hardware.")
    pulse_plan.add_argument("recipe", type=Path)
    pulse_plan.add_argument("--safety-dir", type=Path, default=Path("configs/safety"))
    pulse_plan.add_argument("--preview-points", type=int, default=5)

    pulse = subparsers.add_parser("pulse", help="Run a pulse measurement recipe. Current milestone is dry-run only.")
    pulse.add_argument("recipe", type=Path)
    pulse.add_argument("--dry-run", action="store_true")
    pulse.add_argument("--fake-resistance-ohm", type=float, default=1_000_000.0)
    pulse.add_argument("--fake-noise-std-a", type=float, default=0.0)
    pulse.add_argument("--safety-dir", type=Path, default=Path("configs/safety"))
    pulse.add_argument("--summary", action="store_true")
    pulse.add_argument("--plot", action="store_true")
    pulse.add_argument("--report", action="store_true")
    pulse.add_argument("--progress", action="store_true")
    pulse.add_argument("--index-path", type=Path, default=Path("data/run_index.jsonl"))
    pulse.add_argument("--preview-points", type=int, default=5)

    validate = subparsers.add_parser("validate", help="Validate a Drain I-V recipe without hardware.")
    validate.add_argument("recipe", type=Path)
    validate.add_argument("--safety-dir", type=Path, default=Path("configs/safety"))

    plan = subparsers.add_parser("plan", help="Show the Drain I-V measurement plan without touching hardware.")
    plan.add_argument("recipe", type=Path)
    plan.add_argument("--safety-dir", type=Path, default=Path("configs/safety"))
    plan.add_argument("--preview-points", type=int, default=5, help="Number of leading/trailing planned points to show.")

    scheme_plan = subparsers.add_parser("scheme-plan", help="Show a measurement scheme plan without touching hardware.")
    scheme_plan.add_argument("scheme", type=Path)
    scheme_plan.add_argument("--safety-dir", type=Path, default=Path("configs/safety"))
    scheme_plan.add_argument("--preview-points", type=int, default=3)

    scheme = subparsers.add_parser("scheme", help="Run a measurement scheme YAML file.")
    scheme.add_argument("scheme", type=Path)
    scheme.add_argument("--dry-run", action="store_true")
    scheme.add_argument("--fake-resistance-ohm", type=float, default=10_000_000.0)
    scheme.add_argument("--fake-channel-resistance-ohm", type=float, default=1_000_000.0)
    scheme.add_argument("--fake-gate-leak-resistance-ohm", type=float, default=1_000_000_000.0)
    scheme.add_argument("--fake-gate-modulation-per-v", type=float, default=0.0)
    scheme.add_argument("--fake-noise-std-a", type=float, default=1e-10)
    scheme.add_argument("--safety-dir", type=Path, default=Path("configs/safety"))
    scheme.add_argument("--summary", action="store_true")
    scheme.add_argument("--plot", action="store_true")
    scheme.add_argument("--report", action="store_true")
    scheme.add_argument("--gate-stats", action="store_true")
    scheme.add_argument("--progress", action="store_true")
    scheme.add_argument("--index-path", type=Path, default=Path("data/run_index.jsonl"))
    scheme.add_argument("--yes", action="store_true")
    scheme.add_argument("--preview-points", type=int, default=3)
    scheme.add_argument("--scheme-output-dir", type=Path, default=Path("data/schemes"))
    scheme.add_argument("--batch-csv", action="store_true")
    scheme.add_argument("--batch-points", action="store_true")
    scheme.add_argument("--batch-stats", action="store_true")
    scheme.add_argument("--batch-report", action="store_true")
    scheme.add_argument("--scheme-plot", action="store_true", help="Write scheme_overlay.svg after the scheme.")
    scheme.add_argument("--scheme-runs", action="store_true", help="Write scheme_runs.csv after the scheme.")
    scheme.add_argument("--scheme-points", action="store_true", help="Write scheme_points.csv after the scheme.")
    scheme.add_argument("--scheme-stats", action="store_true", help="Write scheme_stats.csv after the scheme.")

    batch = subparsers.add_parser("batch", help="Run multiple Drain I-V recipes from a batch YAML file.")
    batch.add_argument("batch", type=Path)
    batch.add_argument("--dry-run", action="store_true")
    batch.add_argument("--fake-resistance-ohm", type=float, default=10_000_000.0)
    batch.add_argument("--fake-noise-std-a", type=float, default=1e-10)
    batch.add_argument("--safety-dir", type=Path, default=Path("configs/safety"))
    batch.add_argument("--summary", action="store_true", help="Print a run summary after each recipe.")
    batch.add_argument("--plot", action="store_true", help="Write iv_plot.svg after each recipe.")
    batch.add_argument("--report", action="store_true", help="Write report.md after each recipe.")
    batch.add_argument("--progress", action="store_true", help="Print each measured point while running.")
    batch.add_argument("--index-path", type=Path, default=Path("data/run_index.jsonl"))
    batch.add_argument("--yes", action="store_true", help="Skip the interactive hardware confirmation prompt.")
    batch.add_argument("--preview-points", type=int, default=3, help="Number of leading/trailing planned points to show.")
    batch.add_argument("--continue-on-error", action="store_true", help="Continue remaining recipes after a failed run.")
    batch.add_argument("--batch-output-dir", type=Path, default=Path("data/batches"))
    batch.add_argument("--batch-report", action="store_true", help="Write batch_report.md after the batch.")
    batch.add_argument("--batch-plot", action="store_true", help="Write batch_overlay.svg after the batch.")
    batch.add_argument("--batch-csv", action="store_true", help="Write batch_runs.csv after the batch.")
    batch.add_argument("--batch-points", action="store_true", help="Write combined batch_points.csv after the batch.")
    batch.add_argument("--batch-stats", action="store_true", help="Write batch_stats.csv after the batch.")

    preflight = subparsers.add_parser("preflight", help="Validate recipe, find VISA address, and probe instrument.")
    preflight.add_argument("recipe", type=Path)
    preflight.add_argument("--safety-dir", type=Path, default=Path("configs/safety"))

    new_recipe = subparsers.add_parser("new-recipe", help="Create a starter Drain I-V recipe YAML file.")
    new_recipe.add_argument("output", type=Path)
    new_recipe.add_argument("--mode", choices=["linear_one_way", "forward_backward", "multi_segment"], default="linear_one_way")
    new_recipe.add_argument("--measurement-name", default="drain_iv_new")
    new_recipe.add_argument("--address", default="GPIB0::2::INSTR")
    new_recipe.add_argument("--sample-id", default="")
    new_recipe.add_argument("--device-id", default="")
    new_recipe.add_argument("--cooldown-id", default="")
    new_recipe.add_argument("--contact-geometry", default="")
    new_recipe.add_argument("--contact-notes", default="")
    new_recipe.add_argument("--lab-notebook-ref", default="")
    new_recipe.add_argument("--operator", default="")
    new_recipe.add_argument("--overwrite", action="store_true")

    new_batch = subparsers.add_parser("new-batch", help="Create a starter batch/session YAML file.")
    new_batch.add_argument("output", type=Path)
    new_batch.add_argument("--kind", choices=["smoke_suite", "repeat"], default="repeat")
    new_batch.add_argument("--name", default="new_batch")
    new_batch.add_argument("--recipe", default="configs/recipes/drain_iv_1k_resistor.yaml")
    new_batch.add_argument("--repeat", type=int, default=3)
    new_batch.add_argument("--interval-s", type=float, default=0.5)
    new_batch.add_argument("--overwrite", action="store_true")

    new_scheme = subparsers.add_parser("new-scheme", help="Create a starter measurement scheme YAML file.")
    new_scheme.add_argument("output", type=Path)
    new_scheme.add_argument("--kind", choices=["recipe_and_batch", "repeat_recipe"], default="recipe_and_batch")
    new_scheme.add_argument("--name", default="new_scheme")
    new_scheme.add_argument("--recipe", default="configs/recipes/drain_iv_1k_resistor.yaml")
    new_scheme.add_argument("--batch", default="configs/batches/drain_iv_1k_repeat_linear.yaml")
    new_scheme.add_argument("--repeat", type=int, default=2)
    new_scheme.add_argument("--interval-s", type=float, default=0.5)
    new_scheme.add_argument("--overwrite", action="store_true")

    summarize = subparsers.add_parser("summarize", help="Summarize a saved measurement run.")
    summarize.add_argument("run_dir", type=Path)

    inspect = subparsers.add_parser("inspect-run", help="Inspect metadata, summary, and files for a saved run.")
    inspect.add_argument("run_dir", type=Path)

    plot = subparsers.add_parser("plot", help="Write an SVG I-V plot for a saved measurement run.")
    plot.add_argument("run_dir", type=Path)
    plot.add_argument("--output", type=Path)

    report = subparsers.add_parser("report", help="Write a Markdown report for a saved measurement run.")
    report.add_argument("run_dir", type=Path)
    report.add_argument("--output", type=Path)

    single_gate_summary = subparsers.add_parser("single-gate-summary", help="Summarize a saved single-gate run.")
    single_gate_summary.add_argument("run_dir", type=Path)

    single_gate_plot = subparsers.add_parser("single-gate-plot", help="Write a heatmap SVG for a saved single-gate run.")
    single_gate_plot.add_argument("run_dir", type=Path)
    single_gate_plot.add_argument("--output", type=Path)

    single_gate_report = subparsers.add_parser("single-gate-report", help="Write a Markdown report for a saved single-gate run.")
    single_gate_report.add_argument("run_dir", type=Path)
    single_gate_report.add_argument("--output", type=Path)

    single_gate_stats = subparsers.add_parser("single-gate-stats", help="Write per-gate statistics for a saved single-gate run.")
    single_gate_stats.add_argument("run_dir", type=Path)
    single_gate_stats.add_argument("--output", type=Path)

    check_run = subparsers.add_parser("check-run", help="Evaluate quality checks for a saved run.")
    check_run.add_argument("run_dir", type=Path)

    batch_report = subparsers.add_parser("batch-report", help="Write a Markdown report for a saved batch.")
    batch_report.add_argument("batch_summary_or_dir", type=Path)
    batch_report.add_argument("--output", type=Path)

    batch_plot = subparsers.add_parser("batch-plot", help="Write an overlay SVG plot for a saved batch.")
    batch_plot.add_argument("batch_summary_or_dir", type=Path)
    batch_plot.add_argument("--output", type=Path)

    batch_csv = subparsers.add_parser("batch-csv", help="Write a CSV summary table for a saved batch.")
    batch_csv.add_argument("batch_summary_or_dir", type=Path)
    batch_csv.add_argument("--output", type=Path)

    batch_points = subparsers.add_parser("batch-points", help="Write one long-form CSV with all points from a saved batch.")
    batch_points.add_argument("batch_summary_or_dir", type=Path)
    batch_points.add_argument("--output", type=Path)

    batch_stats = subparsers.add_parser("batch-stats", help="Write grouped stability statistics for a saved batch.")
    batch_stats.add_argument("batch_summary_or_dir", type=Path)
    batch_stats.add_argument("--output", type=Path)

    scheme_report = subparsers.add_parser("scheme-report", help="Write a Markdown report for a saved scheme.")
    scheme_report.add_argument("scheme_summary_or_dir", type=Path)
    scheme_report.add_argument("--output", type=Path)

    scheme_plot = subparsers.add_parser("scheme-plot", help="Write an overlay SVG plot for a saved scheme.")
    scheme_plot.add_argument("scheme_summary_or_dir", type=Path)
    scheme_plot.add_argument("--output", type=Path)

    scheme_runs = subparsers.add_parser("scheme-runs", help="Write a CSV run table for a saved scheme.")
    scheme_runs.add_argument("scheme_summary_or_dir", type=Path)
    scheme_runs.add_argument("--output", type=Path)

    scheme_points = subparsers.add_parser("scheme-points", help="Write one long-form CSV with all points from a saved scheme.")
    scheme_points.add_argument("scheme_summary_or_dir", type=Path)
    scheme_points.add_argument("--output", type=Path)

    scheme_stats = subparsers.add_parser("scheme-stats", help="Write grouped statistics for a saved scheme.")
    scheme_stats.add_argument("scheme_summary_or_dir", type=Path)
    scheme_stats.add_argument("--output", type=Path)

    campaign = subparsers.add_parser("campaign", help="Create a campaign manifest/report from saved data folders.")
    campaign.add_argument("--name", default="campaign")
    campaign.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    campaign.add_argument("--batch-dir", type=Path, default=Path("data/batches"))
    campaign.add_argument("--scheme-dir", type=Path, default=Path("data/schemes"))
    campaign.add_argument("--output-dir", type=Path, default=Path("data/campaigns"))
    campaign.add_argument("--sample")
    campaign.add_argument("--device")
    campaign.add_argument("--tag")
    campaign.add_argument("--qc-status", choices=["PASS", "FAIL", "SKIP", "n/a"])
    campaign.add_argument("--completed-only", action="store_true")
    campaign.add_argument("--incomplete-only", action="store_true")
    campaign.add_argument("--failed-only", action="store_true")
    campaign.add_argument("--measurement-contains")
    campaign.add_argument("--min-resistance-ohm", type=float)
    campaign.add_argument("--max-resistance-ohm", type=float)
    campaign.add_argument("--analytics", action="store_true", help="Write campaign_stats.csv and campaign_resistance_histogram.svg.")

    campaign_report = subparsers.add_parser("campaign-report", help="Rewrite a Markdown report for a saved campaign.")
    campaign_report.add_argument("campaign_manifest_or_dir", type=Path)
    campaign_report.add_argument("--output", type=Path)

    campaign_stats = subparsers.add_parser("campaign-stats", help="Write grouped resistance statistics for a saved campaign.")
    campaign_stats.add_argument("campaign_manifest_or_dir", type=Path)
    campaign_stats.add_argument("--output", type=Path)

    campaign_histogram = subparsers.add_parser("campaign-histogram", help="Write a fitted-resistance histogram SVG for a saved campaign.")
    campaign_histogram.add_argument("campaign_manifest_or_dir", type=Path)
    campaign_histogram.add_argument("--output", type=Path)
    campaign_histogram.add_argument("--bins", type=int, default=12)

    campaign_bundle = subparsers.add_parser("campaign-bundle", help="Create a portable folder and ZIP for a saved campaign.")
    campaign_bundle.add_argument("campaign_manifest_or_dir", type=Path)
    campaign_bundle.add_argument("--output-dir", type=Path, default=Path("data/exports"))
    campaign_bundle.add_argument("--no-points", action="store_true", help="Do not include run points.csv files.")
    campaign_bundle.add_argument("--no-plots", action="store_true", help="Do not include SVG plot files.")
    campaign_bundle.add_argument("--no-reports", action="store_true", help="Do not include Markdown report files.")

    feedback_bundle = subparsers.add_parser("feedback-bundle", help="Create a portable ZIP for sharing one run's lab feedback.")
    feedback_bundle.add_argument("run_dir", type=Path)
    feedback_bundle.add_argument("--output-dir", type=Path, default=Path("data/feedback"))
    feedback_bundle.add_argument("--no-points", action="store_true", help="Do not include points.csv.")
    feedback_bundle.add_argument("--no-plots", action="store_true", help="Do not include SVG plot files.")
    feedback_bundle.add_argument("--no-reports", action="store_true", help="Do not include Markdown report files.")
    feedback_bundle.add_argument(
        "--extra-file",
        type=Path,
        action="append",
        default=[],
        help="Add an extra diagnostic file, such as doctor.json or a GUI session log.",
    )

    list_runs = subparsers.add_parser("list-runs", help="List recent indexed measurement runs.")
    list_runs.add_argument("--index-path", type=Path, default=Path("data/run_index.jsonl"))
    list_runs.add_argument("--limit", type=int, default=10)
    list_runs.add_argument("--sample")
    list_runs.add_argument("--device")
    list_runs.add_argument("--tag")
    list_runs.add_argument("--measurement-type", choices=known_measurement_types())
    list_runs.add_argument("--completed", action="store_true")
    list_runs.add_argument("--failed", action="store_true")
    list_runs.add_argument("--interrupted", action="store_true")

    rebuild = subparsers.add_parser("rebuild-index", help="Rebuild run index from data/raw metadata files.")
    rebuild.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    rebuild.add_argument("--index-path", type=Path, default=Path("data/run_index.jsonl"))

    return parser


def command_list_resources() -> int:
    for resource in list_resources():
        print(resource)
    return 0


def instrument_probe_factory(instrument_id: str):
    if instrument_id == "keithley_2450":
        return None
    if instrument_id == "srs_sr860":
        return probe_srs_sr860
    raise ValueError(f"Unsupported instrument: {instrument_id}")


def open_supported_instrument(instrument_id: str, address: str, timeout_ms: int):
    if instrument_id == "keithley_2450":
        return Keithley2450(address, timeout_ms)
    if instrument_id == "srs_sr860":
        return SRS_SR860(address, timeout_ms)
    raise ValueError(f"Unsupported instrument: {instrument_id}")


def command_doctor(args: argparse.Namespace) -> int:
    report = run_doctor(
        address=args.address,
        timeout_ms=args.timeout_ms,
        probe_factory=instrument_probe_factory(args.instrument),
    )
    if args.output:
        path = write_doctor_report(report, args.output, as_json=args.json)
        print(f"Doctor report: {path}")
    elif args.json:
        print(json.dumps(doctor_report_to_dict(report), indent=2, sort_keys=True))
    else:
        print(format_doctor_report(report))
    return 0 if report.ok else 2


def command_identify(args: argparse.Namespace) -> int:
    smu = open_supported_instrument(args.instrument, args.address, args.timeout_ms)
    try:
        smu.connect()
        print(smu.identify())
        return 0
    finally:
        smu.close()


def command_probe(args: argparse.Namespace) -> int:
    smu = open_supported_instrument(args.instrument, args.address, args.timeout_ms)
    try:
        smu.connect()
        for key, value in smu.probe().items():
            print(f"{key}: {value}")
        return 0
    finally:
        smu.close()


def command_run(args: argparse.Namespace) -> int:
    method = handler_for_measurement_type("drain_iv")
    recipe = method.load_recipe(args.recipe)
    safety = load_named_safety_preset(recipe.safety_preset, args.safety_dir)
    if args.dry_run:
        smu = build_fake_smu(args.fake_resistance_ohm, args.fake_noise_std_a)
    else:
        print(method.format_plan(recipe, args.recipe, args.safety_dir, args.preview_points))
        print()
        preflight_report = run_preflight(args.recipe, args.safety_dir)
        print(format_preflight_report(preflight_report))
        print()
        if not preflight_report.ok:
            print("Run blocked because preflight did not pass.", file=sys.stderr)
            return 2
        if should_confirm_hardware_run(args.dry_run, args.yes) and not confirm_hardware_run():
            print("Run cancelled before hardware output.")
            return 1
        smu = Keithley2450(recipe.instrument.address, recipe.instrument.timeout_ms)

    metadata = execute_recipe_measurement(
        recipe_path=args.recipe,
        recipe=recipe,
        safety=safety,
        smu=smu,
        plot=args.plot,
        report=args.report,
        summary=args.summary,
        progress=args.progress,
        index_path=args.index_path,
    )
    return exit_code_for_metadata(metadata)


def command_single_gate_plan(args: argparse.Namespace) -> int:
    method = handler_for_measurement_type("single_gate_sweep")
    recipe = method.load_recipe(args.recipe)
    print(method.format_plan(recipe, args.recipe, args.safety_dir, args.preview_points))
    return 0


def command_single_gate_preflight(args: argparse.Namespace) -> int:
    report = run_single_gate_preflight(args.recipe, args.safety_dir)
    print(format_single_gate_preflight_report(report))
    return 0 if report.ok else 2


def command_single_gate(args: argparse.Namespace) -> int:
    method = handler_for_measurement_type("single_gate_sweep")
    recipe = method.load_recipe(args.recipe)
    safety = load_named_safety_preset(recipe.safety_preset, args.safety_dir)
    validate_single_gate_recipe_against_safety(recipe, safety)
    print(method.format_plan(recipe, args.recipe, args.safety_dir, args.preview_points))
    print()
    if args.dry_run:
        drain_smu, gate_smu = build_coupled_fake_smus(
            args.fake_channel_resistance_ohm,
            args.fake_gate_leak_resistance_ohm,
            args.fake_gate_modulation_per_v,
            args.fake_noise_std_a,
        )
    else:
        if recipe.drain_instrument.address == recipe.gate_instrument.address:
            print("Single-gate hardware run requires separate drain and gate instrument addresses.", file=sys.stderr)
            return 2
        if not single_gate_hardware_preflight_ok(recipe, args.recipe, args.safety_dir):
            return 2
        if should_confirm_hardware_run(args.dry_run, args.yes) and not confirm_hardware_run(
            lambda prompt: input(prompt.replace("hardware output and sweep", "single-gate hardware output and sweep"))
        ):
            print("Single-gate run cancelled before hardware output.")
            return 1
        drain_smu = Keithley2450(recipe.drain_instrument.address, recipe.drain_instrument.timeout_ms)
        gate_smu = Keithley2450(recipe.gate_instrument.address, recipe.gate_instrument.timeout_ms)
    progress_callback = print_single_gate_progress if args.progress else None
    metadata = run_single_gate_sweep(
        recipe,
        safety,
        drain_smu,
        gate_smu,
        recipe_path=args.recipe,
        progress_callback=progress_callback,
    )
    print(f"CSV: {metadata['csv_path']}")
    print(f"Metadata: {metadata['metadata_path']}")
    print(f"Metadata completed: {metadata['completed']}")
    run_dir = Path(metadata["run_dir"])
    if args.gate_stats and metadata["points_written"] > 0:
        stats_path = write_single_gate_stats_csv(run_dir)
        update_metadata_file(Path(metadata["metadata_path"]), {"single_gate_stats_path": str(stats_path)})
        print(f"Single-gate stats: {stats_path}")
    elif args.gate_stats:
        print("Single-gate stats: skipped because no points were written")
    if args.plot and metadata["points_written"] > 0:
        plot_path = write_single_gate_heatmap_svg(run_dir)
        update_metadata_file(Path(metadata["metadata_path"]), {"single_gate_heatmap_path": str(plot_path)})
        print(f"Single-gate heatmap: {plot_path}")
    elif args.plot:
        print("Single-gate heatmap: skipped because no points were written")
    if args.report and metadata["points_written"] > 0:
        report_path = write_single_gate_report(run_dir)
        update_metadata_file(Path(metadata["metadata_path"]), {"single_gate_report_path": str(report_path)})
        print(f"Single-gate report: {report_path}")
    elif args.report:
        print("Single-gate report: skipped because no points were written")
    indexed_metadata = read_metadata_file(Path(metadata["metadata_path"]))
    written_index_path = append_run_index(indexed_metadata, args.index_path)
    print(f"Index: {written_index_path}")
    if args.summary and metadata["points_written"] > 0:
        print()
        print(format_single_gate_summary(summarize_single_gate_run(run_dir)))
    return exit_code_for_metadata(metadata)


def command_dual_gate_plan(args: argparse.Namespace) -> int:
    method = handler_for_measurement_type("dual_gate_sweep")
    recipe = method.load_recipe(args.recipe)
    print(method.format_plan(recipe, args.recipe, args.safety_dir, args.preview_points))
    return 0


def command_dual_gate(args: argparse.Namespace) -> int:
    method = handler_for_measurement_type("dual_gate_sweep")
    recipe = method.load_recipe(args.recipe)
    safety = load_named_safety_preset(recipe.safety_preset, args.safety_dir)
    validate_dual_gate_recipe_against_safety(recipe, safety)
    print(method.format_plan(recipe, args.recipe, args.safety_dir, args.preview_points))
    print()
    if not args.dry_run:
        print(
            "Dual-gate hardware runs are not active yet. Use --dry-run until the drain/gate1/gate2 hardware topology is smoke-tested.",
            file=sys.stderr,
        )
        return 2
    drain_smu, gate1_smu, gate2_smu = build_dual_gate_fake_smus(
        args.fake_channel_resistance_ohm,
        args.fake_gate1_leak_resistance_ohm,
        args.fake_gate2_leak_resistance_ohm,
        args.fake_gate1_modulation_per_v,
        args.fake_gate2_modulation_per_v,
        args.fake_cross_term_per_v2,
        args.fake_noise_std_a,
    )
    progress_callback = print_dual_gate_progress if args.progress else None
    metadata = run_dual_gate_sweep(
        recipe,
        safety,
        drain_smu,
        gate1_smu,
        gate2_smu,
        recipe_path=args.recipe,
        progress_callback=progress_callback,
    )
    run_dir = Path(metadata["run_dir"])
    print(f"CSV: {metadata['csv_path']}")
    print(f"Metadata: {metadata['metadata_path']}")
    print(f"Metadata completed: {metadata['completed']}")
    if args.gate_stats and metadata["points_written"] > 0:
        stats_path = write_dual_gate_stats_csv(run_dir)
        update_metadata_file(Path(metadata["metadata_path"]), {"dual_gate_stats_path": str(stats_path)})
        print(f"Dual-gate stats: {stats_path}")
    elif args.gate_stats:
        print("Dual-gate stats: skipped because no points were written")
    if args.plot and metadata["points_written"] > 0:
        plot_path = write_dual_gate_heatmap_svg(run_dir)
        update_metadata_file(Path(metadata["metadata_path"]), {"dual_gate_heatmap_path": str(plot_path)})
        print(f"Dual-gate heatmap: {plot_path}")
    elif args.plot:
        print("Dual-gate heatmap: skipped because no points were written")
    if args.report and metadata["points_written"] > 0:
        report_path = write_dual_gate_report(run_dir)
        update_metadata_file(Path(metadata["metadata_path"]), {"dual_gate_report_path": str(report_path)})
        print(f"Dual-gate report: {report_path}")
    elif args.report:
        print("Dual-gate report: skipped because no points were written")
    indexed_metadata = read_metadata_file(Path(metadata["metadata_path"]))
    written_index_path = append_run_index(indexed_metadata, args.index_path)
    print(f"Index: {written_index_path}")
    if args.summary and metadata["points_written"] > 0:
        print()
        print(format_dual_gate_summary(summarize_dual_gate_run(run_dir)))
    return exit_code_for_metadata(metadata)


def command_dual_gate_lockin_plan(args: argparse.Namespace) -> int:
    method = handler_for_measurement_type("dual_gate_lockin_sweep")
    recipe = method.load_recipe(args.recipe)
    print(method.format_plan(recipe, args.recipe, args.safety_dir, args.preview_points))
    return 0


def command_dual_gate_lockin_preflight(args: argparse.Namespace) -> int:
    report = run_dual_gate_lockin_preflight(args.recipe, args.safety_dir)
    print(format_dual_gate_lockin_preflight_report(report))
    return 0 if report.ok else 1


def command_dual_gate_lockin_smoke(args: argparse.Namespace) -> int:
    method = handler_for_measurement_type("dual_gate_lockin_sweep")
    recipe = method.load_recipe(args.recipe)
    safety = load_named_safety_preset(recipe.safety_preset, args.safety_dir)
    validate_dual_gate_lockin_recipe_against_safety(recipe, safety)
    print(format_dual_gate_lockin_smoke_plan(recipe, safety, args.recipe, args.samples, args.interval_s))
    print()
    preflight_text = None
    if args.dry_run:
        lockin = FakeLockIn(
            signal_r_v=args.fake_lockin_r_v,
            phase_deg=args.fake_lockin_phase_deg,
            noise_std_v=args.fake_noise_std,
        )
    else:
        report = run_dual_gate_lockin_preflight(args.recipe, args.safety_dir)
        preflight_text = format_dual_gate_lockin_preflight_report(report)
        print(preflight_text)
        print()
        if not report.ok:
            print("Dual-gate lock-in readout smoke blocked because preflight did not pass.", file=sys.stderr)
            return 2
        lockin = SRS_SR860(recipe.lockin.address or "", recipe.lockin.timeout_ms)
    progress_callback = print_dual_gate_lockin_smoke_progress if args.progress else None
    metadata = run_dual_gate_lockin_readout_smoke(
        recipe,
        safety,
        lockin,
        samples=args.samples,
        interval_s=args.interval_s,
        recipe_path=args.recipe,
        preflight_report=preflight_text,
        progress_callback=progress_callback,
    )
    print(f"CSV: {metadata['csv_path']}")
    print(f"Metadata: {metadata['metadata_path']}")
    print(f"Metadata completed: {metadata['completed']}")
    indexed_metadata = read_metadata_file(Path(metadata["metadata_path"]))
    written_index_path = append_run_index(indexed_metadata, args.index_path)
    print(f"Index: {written_index_path}")
    return exit_code_for_metadata(metadata)


def command_dual_gate_lockin_active_smoke(args: argparse.Namespace) -> int:
    method = handler_for_measurement_type("dual_gate_lockin_sweep")
    recipe = method.load_recipe(args.recipe)
    safety = load_named_safety_preset(recipe.safety_preset, args.safety_dir)
    validate_dual_gate_lockin_recipe_against_safety(recipe, safety)
    print(
        format_dual_gate_lockin_active_smoke_plan(
            recipe,
            safety,
            args.recipe,
            args.gate1_v,
            args.gate2_v,
            args.settle_s,
            args.samples,
            args.interval_s,
        )
    )
    print()
    preflight_text = None
    if args.dry_run:
        gate1_smu, gate2_smu, lockin = build_dual_gate_lockin_fake_instruments(
            args.fake_gate1_leak_resistance_ohm,
            args.fake_gate2_leak_resistance_ohm,
            args.fake_lockin_r_v,
            0.0,
            0.0,
            0.0,
            args.fake_lockin_phase_deg,
            args.fake_noise_std,
        )
    else:
        report = run_dual_gate_lockin_preflight(args.recipe, args.safety_dir)
        preflight_text = format_dual_gate_lockin_preflight_report(report)
        print(preflight_text)
        print()
        if not report.ok:
            print("Dual-gate lock-in active-gate smoke blocked because preflight did not pass.", file=sys.stderr)
            return 2
        if should_confirm_hardware_run(False, args.yes) and not confirm_hardware_run(
            lambda prompt: input(prompt.replace("hardware output and sweep", "dual-gate active-gate smoke output"))
        ):
            print("Dual-gate lock-in active-gate smoke cancelled before output was enabled.", file=sys.stderr)
            return 2
        gate1_smu = Keithley2450(recipe.gate1_instrument.address, recipe.gate1_instrument.timeout_ms)
        gate2_smu = Keithley2450(recipe.gate2_instrument.address, recipe.gate2_instrument.timeout_ms)
        lockin = SRS_SR860(recipe.lockin.address or "", recipe.lockin.timeout_ms)
    progress_callback = print_dual_gate_lockin_active_smoke_progress if args.progress else None
    metadata = run_dual_gate_lockin_active_gate_smoke(
        recipe,
        safety,
        gate1_smu,
        gate2_smu,
        lockin,
        gate1_voltage_v=args.gate1_v,
        gate2_voltage_v=args.gate2_v,
        samples=args.samples,
        interval_s=args.interval_s,
        settle_s=args.settle_s,
        recipe_path=args.recipe,
        preflight_report=preflight_text,
        progress_callback=progress_callback,
    )
    print(f"CSV: {metadata['csv_path']}")
    print(f"Metadata: {metadata['metadata_path']}")
    print(f"Metadata completed: {metadata['completed']}")
    indexed_metadata = read_metadata_file(Path(metadata["metadata_path"]))
    written_index_path = append_run_index(indexed_metadata, args.index_path)
    print(f"Index: {written_index_path}")
    return exit_code_for_metadata(metadata)


def command_dual_gate_lockin(args: argparse.Namespace) -> int:
    method = handler_for_measurement_type("dual_gate_lockin_sweep")
    recipe = method.load_recipe(args.recipe)
    safety = load_named_safety_preset(recipe.safety_preset, args.safety_dir)
    validate_dual_gate_lockin_recipe_against_safety(recipe, safety)
    print(method.format_plan(recipe, args.recipe, args.safety_dir, args.preview_points))
    print()
    if not args.dry_run and not args.allow_active_sweep:
        report = run_dual_gate_lockin_preflight(args.recipe, args.safety_dir)
        print(format_dual_gate_lockin_preflight_report(report))
        print()
        print(
            "Dual-gate lock-in hardware sweep is guarded. Use --allow-active-sweep only after preflight, readout smoke, and active-gate smoke pass.",
            file=sys.stderr,
        )
        return 2
    if args.dry_run:
        gate1_smu, gate2_smu, lockin = build_dual_gate_lockin_fake_instruments(
            args.fake_gate1_leak_resistance_ohm,
            args.fake_gate2_leak_resistance_ohm,
            args.fake_lockin_r_v,
            args.fake_lockin_gate1_sensitivity_v_per_v,
            args.fake_lockin_gate2_sensitivity_v_per_v,
            args.fake_lockin_cross_sensitivity_v_per_v2,
            args.fake_lockin_phase_deg,
            args.fake_noise_std,
        )
    else:
        total_points = dual_gate_lockin_point_count(recipe)
        if args.max_hardware_points < 1:
            raise ValueError("--max-hardware-points must be >= 1")
        if total_points > args.max_hardware_points:
            print(
                f"Dual-gate lock-in active sweep blocked: {total_points} points exceeds --max-hardware-points {args.max_hardware_points}.",
                file=sys.stderr,
            )
            return 2
        report = run_dual_gate_lockin_preflight(args.recipe, args.safety_dir)
        print(format_dual_gate_lockin_preflight_report(report))
        print()
        if not report.ok:
            print("Dual-gate lock-in active sweep blocked because preflight did not pass.", file=sys.stderr)
            return 2
        if should_confirm_hardware_run(False, args.yes) and not confirm_hardware_run(
            lambda prompt: input(prompt.replace("hardware output and sweep", "dual-gate lock-in active sweep"))
        ):
            print("Dual-gate lock-in active sweep cancelled before output was enabled.", file=sys.stderr)
            return 2
        gate1_smu = Keithley2450(recipe.gate1_instrument.address, recipe.gate1_instrument.timeout_ms)
        gate2_smu = Keithley2450(recipe.gate2_instrument.address, recipe.gate2_instrument.timeout_ms)
        lockin = SRS_SR860(recipe.lockin.address or "", recipe.lockin.timeout_ms)
    progress_callback = print_dual_gate_lockin_progress if args.progress else None
    metadata = run_dual_gate_lockin_sweep(
        recipe,
        safety,
        gate1_smu,
        gate2_smu,
        lockin,
        recipe_path=args.recipe,
        progress_callback=progress_callback,
    )
    run_dir = Path(metadata["run_dir"])
    print(f"CSV: {metadata['csv_path']}")
    print(f"Metadata: {metadata['metadata_path']}")
    print(f"Metadata completed: {metadata['completed']}")
    if args.gate_stats and metadata["points_written"] > 0:
        stats_path = write_dual_gate_lockin_stats_csv(run_dir)
        update_metadata_file(Path(metadata["metadata_path"]), {"dual_gate_lockin_stats_path": str(stats_path)})
        print(f"Dual-gate lock-in stats: {stats_path}")
    elif args.gate_stats:
        print("Dual-gate lock-in stats: skipped because no points were written")
    if args.plot and metadata["points_written"] > 0:
        plot_path = write_dual_gate_lockin_heatmap_svg(run_dir)
        update_metadata_file(Path(metadata["metadata_path"]), {"dual_gate_lockin_heatmap_path": str(plot_path)})
        print(f"Dual-gate lock-in heatmap: {plot_path}")
    elif args.plot:
        print("Dual-gate lock-in heatmap: skipped because no points were written")
    if args.report and metadata["points_written"] > 0:
        report_path = write_dual_gate_lockin_report(run_dir)
        update_metadata_file(Path(metadata["metadata_path"]), {"dual_gate_lockin_report_path": str(report_path)})
        print(f"Dual-gate lock-in report: {report_path}")
    elif args.report:
        print("Dual-gate lock-in report: skipped because no points were written")
    indexed_metadata = read_metadata_file(Path(metadata["metadata_path"]))
    written_index_path = append_run_index(indexed_metadata, args.index_path)
    print(f"Index: {written_index_path}")
    if args.summary and metadata["points_written"] > 0:
        print()
        print(format_dual_gate_lockin_summary(summarize_dual_gate_lockin_run(run_dir)))
    return exit_code_for_metadata(metadata)


def command_ac_lockin_plan(args: argparse.Namespace) -> int:
    method = handler_for_measurement_type("ac_lockin_sweep")
    recipe = method.load_recipe(args.recipe)
    print(method.format_plan(recipe, args.recipe, args.safety_dir, args.preview_points))
    return 0


def command_ac_lockin_preflight(args: argparse.Namespace) -> int:
    report = run_ac_lockin_preflight(args.recipe, args.safety_dir)
    print(format_ac_lockin_preflight_report(report))
    return 0 if report.ok else 2


def command_ac_lockin(args: argparse.Namespace) -> int:
    method = handler_for_measurement_type("ac_lockin_sweep")
    recipe = method.load_recipe(args.recipe)
    safety = load_named_safety_preset(recipe.safety_preset, args.safety_dir)
    validate_ac_lockin_recipe_against_safety(recipe, safety)
    print(method.format_plan(recipe, args.recipe, args.safety_dir, args.preview_points))
    print()
    if args.dry_run:
        source_smu = build_fake_smu(args.fake_resistance_ohm, args.fake_noise_std)
        lockin = FakeLockIn(
            signal_r_v=args.fake_lockin_r_v,
            phase_deg=args.fake_lockin_phase_deg,
            noise_std_v=args.fake_noise_std,
        )
    else:
        report = run_ac_lockin_preflight(args.recipe, args.safety_dir)
        print(format_ac_lockin_preflight_report(report))
        print()
        if not report.ok:
            print("AC lock-in hardware run blocked because preflight did not pass.", file=sys.stderr)
            return 2
        if should_confirm_hardware_run(args.dry_run, args.yes) and not confirm_hardware_run(
            lambda prompt: input(prompt.replace("hardware output and sweep", "AC lock-in hardware output and sweep"))
        ):
            print("AC lock-in run cancelled before hardware output.")
            return 1
        source_smu = Keithley2450(recipe.source_instrument.address, recipe.source_instrument.timeout_ms)
        lockin = SRS_SR860(recipe.lockin.address or "", recipe.lockin.timeout_ms)
    progress_callback = print_ac_lockin_progress if args.progress else None
    metadata = run_ac_lockin_sweep(
        recipe,
        safety,
        source_smu,
        lockin,
        recipe_path=args.recipe,
        progress_callback=progress_callback,
    )
    run_dir = Path(metadata["run_dir"])
    print(f"CSV: {metadata['csv_path']}")
    print(f"Metadata: {metadata['metadata_path']}")
    print(f"Metadata completed: {metadata['completed']}")
    if args.plot and metadata["points_written"] > 0:
        plot_path = write_ac_lockin_plot_svg(run_dir)
        update_metadata_file(Path(metadata["metadata_path"]), {"ac_lockin_plot_path": str(plot_path)})
        print(f"AC lock-in plot: {plot_path}")
    elif args.plot:
        print("AC lock-in plot: skipped because no points were written")
    if args.report and metadata["points_written"] > 0:
        report_path = write_ac_lockin_report(run_dir)
        update_metadata_file(Path(metadata["metadata_path"]), {"ac_lockin_report_path": str(report_path)})
        print(f"AC lock-in report: {report_path}")
    elif args.report:
        print("AC lock-in report: skipped because no points were written")
    indexed_metadata = read_metadata_file(Path(metadata["metadata_path"]))
    written_index_path = append_run_index(indexed_metadata, args.index_path)
    print(f"Index: {written_index_path}")
    if args.summary and metadata["points_written"] > 0:
        print()
        print(method.format_summary(method.summarize(run_dir)))
    return exit_code_for_metadata(metadata)


def command_pulse_plan(args: argparse.Namespace) -> int:
    method = handler_for_measurement_type("pulse_measurement")
    recipe = method.load_recipe(args.recipe)
    print(method.format_plan(recipe, args.recipe, args.safety_dir, args.preview_points))
    return 0


def command_pulse(args: argparse.Namespace) -> int:
    method = handler_for_measurement_type("pulse_measurement")
    recipe = method.load_recipe(args.recipe)
    safety = load_named_safety_preset(recipe.safety_preset, args.safety_dir)
    validate_pulse_recipe_against_safety(recipe, safety)
    print(method.format_plan(recipe, args.recipe, args.safety_dir, args.preview_points))
    print()
    if not args.dry_run:
        print("Pulse hardware runs are not active yet. Use --dry-run for this milestone.", file=sys.stderr)
        return 2
    source_smu = build_fake_smu(args.fake_resistance_ohm, args.fake_noise_std_a)
    progress_callback = print_pulse_progress if args.progress else None
    metadata = run_pulse_measurement(
        recipe,
        safety,
        source_smu,
        recipe_path=args.recipe,
        progress_callback=progress_callback,
        sleep=False,
    )
    run_dir = Path(metadata["run_dir"])
    print(f"CSV: {metadata['csv_path']}")
    print(f"Metadata: {metadata['metadata_path']}")
    print(f"Metadata completed: {metadata['completed']}")
    if args.plot and metadata["points_written"] > 0:
        plot_path = write_pulse_plot_svg(run_dir)
        update_metadata_file(Path(metadata["metadata_path"]), {"pulse_plot_path": str(plot_path)})
        print(f"Pulse plot: {plot_path}")
    elif args.plot:
        print("Pulse plot: skipped because no points were written")
    if args.report and metadata["points_written"] > 0:
        report_path = write_pulse_report(run_dir)
        update_metadata_file(Path(metadata["metadata_path"]), {"pulse_report_path": str(report_path)})
        print(f"Pulse report: {report_path}")
    elif args.report:
        print("Pulse report: skipped because no points were written")
    quality_report = evaluate_run_quality(run_dir)
    update_metadata_file(Path(metadata["metadata_path"]), {"quality": quality_report_to_dict(quality_report)})
    print(format_quality_report(quality_report))
    indexed_metadata = read_metadata_file(Path(metadata["metadata_path"]))
    written_index_path = append_run_index(indexed_metadata, args.index_path)
    print(f"Index: {written_index_path}")
    if args.summary and metadata["points_written"] > 0:
        print()
        print(method.format_summary(method.summarize(run_dir)))
    return exit_code_for_metadata(metadata)


def single_gate_hardware_preflight_ok(
    recipe,
    recipe_path: str | Path,
    safety_dir: str | Path = "configs/safety",
) -> bool:
    report = run_single_gate_preflight_for_recipe(recipe, recipe_path, safety_dir)
    print(format_single_gate_preflight_report(report))
    if not report.ok:
        print("Single-gate run blocked because preflight did not pass.", file=sys.stderr)
    return report.ok


def execute_recipe_measurement(
    recipe_path: Path,
    recipe,
    safety,
    smu,
    plot: bool,
    report: bool,
    summary: bool,
    progress: bool,
    index_path: Path,
    progress_prefix: str = "",
) -> dict:
    if progress and progress_prefix:
        progress_callback = lambda point, total: print_progress(point, total, prefix=progress_prefix)
    elif progress:
        progress_callback = print_progress
    else:
        progress_callback = None
    metadata = run_drain_iv(
        recipe,
        safety,
        smu,
        recipe_path=recipe_path,
        progress_callback=progress_callback,
    )
    run_dir = Path(metadata["run_dir"])
    if plot and metadata["points_written"] > 0:
        plot_path = write_iv_svg(run_dir)
        metadata["plot_path"] = str(plot_path)
        update_metadata_file(Path(metadata["metadata_path"]), {"plot_path": str(plot_path)})
        print(f"Plot: {plot_path}")
    elif plot:
        print("Plot: skipped because no points were written")
    print(f"CSV: {metadata['csv_path']}")
    print(f"Metadata: {metadata['metadata_path']}")
    print(f"Metadata completed: {metadata['completed']}")
    quality_report = evaluate_run_quality(run_dir)
    metadata["quality"] = quality_report_to_dict(quality_report)
    update_metadata_file(Path(metadata["metadata_path"]), {"quality": metadata["quality"]})
    print(format_quality_report(quality_report))
    if report:
        report_path = write_run_report(run_dir)
        metadata["report_path"] = str(report_path)
        update_metadata_file(Path(metadata["metadata_path"]), {"report_path": str(report_path)})
        print(f"Report: {report_path}")
    indexed_metadata = read_metadata_file(Path(metadata["metadata_path"]))
    written_index_path = append_run_index(indexed_metadata, index_path)
    print(f"Index: {written_index_path}")
    if summary:
        print()
        print(format_summary(summarize_run(run_dir)))
    return metadata


def build_fake_smu(resistance_ohm: float, noise_std_a: float) -> FakeSMU:
    if resistance_ohm <= 0:
        raise ValueError("--fake-resistance-ohm must be > 0")
    if noise_std_a < 0:
        raise ValueError("--fake-noise-std-a must be >= 0")
    return FakeSMU(resistance_ohm=resistance_ohm, noise_std_a=noise_std_a)


def build_coupled_fake_smus(
    channel_resistance_ohm: float,
    gate_leak_resistance_ohm: float,
    gate_modulation_per_v: float,
    noise_std_a: float,
) -> tuple[CoupledFakeSMU, CoupledFakeSMU]:
    if channel_resistance_ohm <= 0:
        raise ValueError("--fake-channel-resistance-ohm must be > 0")
    if gate_leak_resistance_ohm <= 0:
        raise ValueError("--fake-gate-leak-resistance-ohm must be > 0")
    if noise_std_a < 0:
        raise ValueError("--fake-noise-std-a must be >= 0")
    state = CoupledFakeDeviceState(
        channel_resistance_ohm=channel_resistance_ohm,
        gate_leak_resistance_ohm=gate_leak_resistance_ohm,
        gate_modulation_per_v=gate_modulation_per_v,
        noise_std_a=noise_std_a,
    )
    return CoupledFakeSMU("drain", state), CoupledFakeSMU("gate", state)


def build_dual_gate_fake_smus(
    channel_resistance_ohm: float,
    gate1_leak_resistance_ohm: float,
    gate2_leak_resistance_ohm: float,
    gate1_modulation_per_v: float,
    gate2_modulation_per_v: float,
    cross_term_per_v2: float,
    noise_std_a: float,
) -> tuple[DualGateFakeSMU, DualGateFakeSMU, DualGateFakeSMU]:
    if channel_resistance_ohm <= 0:
        raise ValueError("--fake-channel-resistance-ohm must be > 0")
    if gate1_leak_resistance_ohm <= 0:
        raise ValueError("--fake-gate1-leak-resistance-ohm must be > 0")
    if gate2_leak_resistance_ohm <= 0:
        raise ValueError("--fake-gate2-leak-resistance-ohm must be > 0")
    if noise_std_a < 0:
        raise ValueError("--fake-noise-std-a must be >= 0")
    state = DualGateFakeDeviceState(
        channel_resistance_ohm=channel_resistance_ohm,
        gate1_leak_resistance_ohm=gate1_leak_resistance_ohm,
        gate2_leak_resistance_ohm=gate2_leak_resistance_ohm,
        gate1_modulation_per_v=gate1_modulation_per_v,
        gate2_modulation_per_v=gate2_modulation_per_v,
        cross_term_per_v2=cross_term_per_v2,
        noise_std_a=noise_std_a,
    )
    return DualGateFakeSMU("drain", state), DualGateFakeSMU("gate1", state), DualGateFakeSMU("gate2", state)


def build_dual_gate_lockin_fake_instruments(
    gate1_leak_resistance_ohm: float,
    gate2_leak_resistance_ohm: float,
    lockin_r_v: float,
    lockin_gate1_sensitivity_v_per_v: float,
    lockin_gate2_sensitivity_v_per_v: float,
    lockin_cross_sensitivity_v_per_v2: float,
    lockin_phase_deg: float,
    noise_std_v: float,
) -> tuple[DualGateFakeSMU, DualGateFakeSMU, DualGateFakeLockIn]:
    if gate1_leak_resistance_ohm <= 0:
        raise ValueError("--fake-gate1-leak-resistance-ohm must be > 0")
    if gate2_leak_resistance_ohm <= 0:
        raise ValueError("--fake-gate2-leak-resistance-ohm must be > 0")
    if lockin_r_v < 0:
        raise ValueError("--fake-lockin-r-v must be >= 0")
    if noise_std_v < 0:
        raise ValueError("--fake-noise-std must be >= 0")
    state = DualGateFakeDeviceState(
        gate1_leak_resistance_ohm=gate1_leak_resistance_ohm,
        gate2_leak_resistance_ohm=gate2_leak_resistance_ohm,
    )
    lockin = DualGateFakeLockIn(
        state,
        base_r_v=lockin_r_v,
        gate1_sensitivity_v_per_v=lockin_gate1_sensitivity_v_per_v,
        gate2_sensitivity_v_per_v=lockin_gate2_sensitivity_v_per_v,
        cross_sensitivity_v_per_v2=lockin_cross_sensitivity_v_per_v2,
        phase_deg=lockin_phase_deg,
        noise_std_v=noise_std_v,
    )
    return DualGateFakeSMU("gate1", state), DualGateFakeSMU("gate2", state), lockin


def exit_code_for_metadata(metadata: dict) -> int:
    if metadata["error_type"]:
        print(f"Error: {metadata['error_type']}: {metadata['error_message']}", file=sys.stderr)
        if metadata.get("interrupted"):
            return 130
        return 2
    return 0


def should_confirm_hardware_run(dry_run: bool, yes: bool) -> bool:
    return not dry_run and not yes


def confirm_hardware_run(input_func: Callable[[str], str] = input) -> bool:
    answer = input_func("Proceed with hardware output and sweep? [y/N]: ")
    return answer.strip().lower() in {"y", "yes"}


def print_progress(point: MeasurementPoint, total_points: int, prefix: str = "") -> None:
    label = f"{prefix} " if prefix else ""
    print(
        (
            f"{label}[{point.index + 1}/{total_points}] "
            f"V={point.voltage_v:.6g} V, "
            f"I={point.current_a:.6g} A, "
            f"t={point.elapsed_s:.3f} s"
        ),
        flush=True,
    )


def print_single_gate_progress(point, total_points: int) -> None:
    print(
        (
            f"[{point.index + 1}/{total_points}] "
            f"Vg={point.gate_voltage_v:.6g} V, "
            f"Vd={point.drain_voltage_v:.6g} V, "
            f"Id={point.drain_current_a:.6g} A, "
            f"Ig={point.gate_current_a:.6g} A, "
            f"t={point.elapsed_s:.3f} s"
        ),
        flush=True,
    )


def print_dual_gate_progress(point, total_points: int) -> None:
    print(
        (
            f"[{point.index + 1}/{total_points}] "
            f"Vg1={point.gate1_voltage_v:.6g} V, "
            f"Vg2={point.gate2_voltage_v:.6g} V, "
            f"Vd={point.drain_voltage_v:.6g} V, "
            f"Id={point.drain_current_a:.6g} A, "
            f"Ig1={point.gate1_current_a:.6g} A, "
            f"Ig2={point.gate2_current_a:.6g} A, "
            f"t={point.elapsed_s:.3f} s"
        ),
        flush=True,
    )


def print_dual_gate_lockin_progress(point, total_points: int) -> None:
    print(
        (
            f"[{point.index + 1}/{total_points}] "
            f"Vg1={point.gate1_voltage_v:.6g} V, "
            f"Vg2={point.gate2_voltage_v:.6g} V, "
            f"Ig1={point.gate1_current_a:.6g} A, "
            f"Ig2={point.gate2_current_a:.6g} A, "
            f"R={point.lockin_r_v:.6g} V, "
            f"theta={point.lockin_theta_deg:.6g} deg, "
            f"t={point.elapsed_s:.3f} s"
        ),
        flush=True,
    )


def print_dual_gate_lockin_smoke_progress(point, total_points: int) -> None:
    print(
        "Smoke "
        f"{point.sample_index + 1}/{total_points}: "
        f"R={format_optional_float(point.lockin_r_v)} V, "
        f"theta={format_optional_float(point.lockin_theta_deg)} deg, "
        f"X={format_optional_float(point.lockin_x_v)} V, "
        f"Y={format_optional_float(point.lockin_y_v)} V"
    )


def print_dual_gate_lockin_active_smoke_progress(point, total_points: int) -> None:
    print(
        "Active smoke "
        f"{point.sample_index + 1}/{total_points}: "
        f"Vg1={point.gate1_voltage_v:.6g} V, "
        f"Ig1={point.gate1_current_a:.6g} A, "
        f"Vg2={point.gate2_voltage_v:.6g} V, "
        f"Ig2={point.gate2_current_a:.6g} A, "
        f"R={format_optional_float(point.lockin_r_v)} V, "
        f"theta={format_optional_float(point.lockin_theta_deg)} deg"
    )


def format_optional_float(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.6g}"


def print_ac_lockin_progress(point, total_points: int) -> None:
    print(
        (
            f"[{point.index + 1}/{total_points}] "
            f"Vbias={point.bias_voltage_v:.6g} V, "
            f"Isrc={point.source_current_a:.6g} A, "
            f"R={point.lockin_r_v:.6g} V, "
            f"theta={point.lockin_theta_deg:.6g} deg, "
            f"t={point.elapsed_s:.3f} s"
        ),
        flush=True,
    )


def print_pulse_progress(point, total_points: int) -> None:
    print(
        (
            f"[{point.index + 1}/{total_points}] "
            f"Vpulse={point.pulse_voltage_v:.6g} V, "
            f"Isrc={point.source_current_a:.6g} A, "
            f"width={point.width_s:.6g} s, "
            f"duty={point.duty_cycle:.6g}, "
            f"t={point.elapsed_s:.3f} s"
        ),
        flush=True,
    )



def command_validate(args: argparse.Namespace) -> int:
    print(format_validation_report(validate_recipe_file(args.recipe, args.safety_dir)))
    return 0


def command_plan(args: argparse.Namespace) -> int:
    method = handler_for_measurement_type("drain_iv")
    recipe = method.load_recipe(args.recipe)
    print(method.format_plan(recipe, args.recipe, args.safety_dir, args.preview_points))
    return 0


def command_scheme_plan(args: argparse.Namespace) -> int:
    scheme = load_scheme(args.scheme)
    print(format_scheme_plan(scheme, args.scheme, args.safety_dir, args.preview_points))
    return 0


def command_batch(args: argparse.Namespace) -> int:
    batch = load_batch(args.batch)
    entries = resolve_batch_entries(batch, args.batch)
    if not entries:
        print("Batch has no enabled recipes.", file=sys.stderr)
        return 2

    print(format_batch_plan(batch, args.batch, args.safety_dir, args.preview_points))
    print()

    if not args.dry_run:
        preflight_failed = False
        for entry in entries:
            print(f"=== Preflight: {entry.label} ===")
            report = run_preflight(entry.recipe_path, args.safety_dir)
            print(format_preflight_report(report))
            print()
            if not report.ok:
                preflight_failed = True
        if preflight_failed:
            print("Batch blocked because one or more preflight checks did not pass.", file=sys.stderr)
            return 2
        if should_confirm_hardware_run(args.dry_run, args.yes) and not confirm_hardware_run():
            print("Batch cancelled before hardware output.")
            return 1

    batch_dir, batch_summary = create_batch_summary(batch, args.batch, args.dry_run, args.batch_output_dir)
    print(f"Batch summary directory: {batch_dir}")
    stop_on_error = batch.stop_on_error and not args.continue_on_error
    worst_exit_code = 0

    try:
        for number, entry in enumerate(entries, start=1):
            print()
            print(f"=== Running {number}/{len(entries)}: {entry.label} ===")
            recipe = load_recipe(entry.recipe_path)
            safety = load_named_safety_preset(recipe.safety_preset, args.safety_dir)
            if args.dry_run:
                smu = build_fake_smu(args.fake_resistance_ohm, args.fake_noise_std_a)
            else:
                smu = Keithley2450(recipe.instrument.address, recipe.instrument.timeout_ms)
            metadata = execute_recipe_measurement(
                recipe_path=entry.recipe_path,
                recipe=recipe,
                safety=safety,
                smu=smu,
                plot=args.plot,
                report=args.report,
                summary=args.summary,
                progress=args.progress,
                index_path=args.index_path,
                progress_prefix=f"[{entry.label}]",
            )
            batch_summary["runs"].append(
                {
                    "label": entry.label,
                    "base_label": entry.base_label,
                    "repeat_index": entry.repeat_index,
                    "repeat_count": entry.repeat_count,
                    "recipe_path": str(entry.recipe_path),
                    "completed": metadata.get("completed"),
                    "interrupted": metadata.get("interrupted"),
                    "error_type": metadata.get("error_type"),
                    "error_message": metadata.get("error_message"),
                    "points_written": metadata.get("points_written"),
                    "run_dir": metadata.get("run_dir"),
                    "metadata_path": metadata.get("metadata_path"),
                    "csv_path": metadata.get("csv_path"),
                    "plot_path": metadata.get("plot_path"),
                    "report_path": metadata.get("report_path"),
                    "quality": metadata.get("quality"),
                }
            )
            exit_code = exit_code_for_metadata(metadata)
            worst_exit_code = max(worst_exit_code, exit_code)
            if exit_code != 0 and stop_on_error:
                print("Batch stopped after failed recipe.")
                break
            if entry.interval_s > 0 and number < len(entries):
                print(f"Waiting {entry.interval_s:.6g} s before next batch entry...")
                time.sleep(entry.interval_s)
    finally:
        summary_path = finish_batch_summary(batch_dir, batch_summary)
        batch_quality = evaluate_batch_quality(summary_path)
        update_batch_summary_quality(summary_path, batch_quality)
        print(format_batch_quality(batch_quality))
        if batch_quality.get("status") == "FAIL":
            worst_exit_code = max(worst_exit_code, 2)
        if args.batch_csv:
            csv_path = write_batch_runs_csv(summary_path)
            print(f"Batch CSV: {csv_path}")
        if args.batch_points:
            points_path = write_batch_points_csv(summary_path)
            print(f"Batch points: {points_path}")
        if args.batch_stats:
            stats_path = write_batch_stats_csv(summary_path)
            print(f"Batch stats: {stats_path}")
        if args.batch_plot:
            plot_path = write_batch_overlay_svg(summary_path)
            print(f"Batch plot: {plot_path}")
        if args.batch_report:
            report_path = write_batch_report(summary_path)
            print(f"Batch report: {report_path}")
        print()
        print(f"Batch summary: {summary_path}")
        print(f"Batch completed: {batch_summary['completed']}")

    return worst_exit_code


def command_scheme(args: argparse.Namespace) -> int:
    scheme = load_scheme(args.scheme)
    steps = resolve_scheme_steps(scheme, args.scheme)
    if not steps:
        print("Scheme has no enabled steps.", file=sys.stderr)
        return 2
    print(format_scheme_plan(scheme, args.scheme, args.safety_dir, args.preview_points))
    print()

    if not args.dry_run:
        if not preflight_scheme_steps(steps, args.safety_dir):
            print("Scheme blocked because one or more preflight checks did not pass.", file=sys.stderr)
            return 2
        if should_confirm_hardware_run(args.dry_run, args.yes) and not confirm_hardware_run(
            lambda prompt: input(prompt.replace("hardware output and sweep", "scheme hardware output and sweeps"))
        ):
            print("Scheme cancelled before hardware output.")
            return 1

    scheme_dir, scheme_summary = create_scheme_summary(scheme, args.scheme, args.dry_run, args.scheme_output_dir)
    print(f"Scheme summary directory: {scheme_dir}")
    worst_exit_code = 0
    try:
        for number, step in enumerate(steps, start=1):
            print()
            print(f"=== Scheme step {number}/{len(steps)}: {step.label} ({step.type}) ===")
            if step.type == "drain_iv":
                metadata = run_scheme_drain_iv_step(args, step)
                scheme_summary["steps"].append(
                    {
                        "label": step.label,
                        "type": step.type,
                        "path": str(step.path),
                        "overrides": step.overrides.model_dump(mode="json", exclude_none=True)
                        if step.overrides is not None
                        else None,
                        "repeat_index": step.repeat_index,
                        "repeat_count": step.repeat_count,
                        "matrix_label": step.matrix_label,
                        "matrix_index": step.matrix_index,
                        "matrix_count": step.matrix_count,
                        "completed": metadata.get("completed"),
                        "error_type": metadata.get("error_type"),
                        "run_dir": metadata.get("run_dir"),
                        "metadata_path": metadata.get("metadata_path"),
                        "quality": metadata.get("quality"),
                    }
                )
                exit_code = exit_code_for_metadata(metadata)
            elif step.type == "single_gate":
                metadata = run_scheme_single_gate_step(args, step)
                scheme_summary["steps"].append(
                    {
                        "label": step.label,
                        "type": step.type,
                        "path": str(step.path),
                        "repeat_index": step.repeat_index,
                        "repeat_count": step.repeat_count,
                        "matrix_label": step.matrix_label,
                        "matrix_index": step.matrix_index,
                        "matrix_count": step.matrix_count,
                        "completed": metadata.get("completed"),
                        "error_type": metadata.get("error_type"),
                        "run_dir": metadata.get("run_dir"),
                        "metadata_path": metadata.get("metadata_path"),
                    }
                )
                exit_code = exit_code_for_metadata(metadata)
            else:
                exit_code, batch_summary_path = run_scheme_batch_step(args, step, scheme_dir)
                batch_completed = False
                if batch_summary_path is not None:
                    batch_data = read_metadata_file(batch_summary_path)
                    batch_completed = bool(batch_data.get("completed"))
                scheme_summary["steps"].append(
                    {
                        "label": step.label,
                        "type": step.type,
                        "path": str(step.path),
                        "repeat_index": step.repeat_index,
                        "repeat_count": step.repeat_count,
                        "matrix_label": step.matrix_label,
                        "matrix_index": step.matrix_index,
                        "matrix_count": step.matrix_count,
                        "completed": batch_completed and exit_code == 0,
                        "error_type": None if exit_code == 0 else "BatchStepFailed",
                        "batch_summary_path": str(batch_summary_path) if batch_summary_path is not None else None,
                    }
                )
            worst_exit_code = max(worst_exit_code, exit_code)
            if exit_code != 0 and scheme.stop_on_error:
                print("Scheme stopped after failed step.")
                break
            if step.interval_s > 0 and number < len(steps):
                print(f"Waiting {step.interval_s:.6g} s before next scheme step...")
                time.sleep(step.interval_s)
    finally:
        summary_path = finish_scheme_summary(scheme_dir, scheme_summary)
        scheme_quality = evaluate_scheme_quality(summary_path)
        update_scheme_summary_quality(summary_path, scheme_quality)
        print(format_scheme_quality(scheme_quality))
        if scheme_quality.get("status") == "FAIL":
            worst_exit_code = max(worst_exit_code, 2)
        if args.scheme_runs:
            runs_path = write_scheme_runs_csv(summary_path)
            print(f"Scheme runs CSV: {runs_path}")
        if args.scheme_points:
            points_path = write_scheme_points_csv(summary_path)
            print(f"Scheme points CSV: {points_path}")
        if args.scheme_stats:
            stats_path = write_scheme_stats_csv(summary_path)
            print(f"Scheme stats CSV: {stats_path}")
        if args.scheme_plot:
            plot_path = write_scheme_overlay_svg(summary_path)
            print(f"Scheme plot: {plot_path}")
        report_path = write_scheme_review_report(summary_path)
        csv_path = write_scheme_steps_csv(summary_path)
        print()
        print(f"Scheme summary: {summary_path}")
        print(f"Scheme report: {report_path}")
        print(f"Scheme CSV: {csv_path}")
        print(f"Scheme completed: {scheme_summary['completed']}")
    return worst_exit_code


def preflight_scheme_steps(steps, safety_dir: Path) -> bool:
    ok = True
    for step in steps:
        if step.type == "drain_iv":
            recipe = load_scheme_step_recipe(step)
            print(f"Preflight for scheme step {step.label}: {step.path}")
            report = run_preflight_for_recipe(recipe, step.path, safety_dir)
            print(format_preflight_report(report))
            print()
            if not report.ok:
                ok = False
        elif step.type == "single_gate":
            recipe = load_scheme_step_single_gate_recipe(step)
            print(f"Preflight for scheme step {step.label}: {step.path}")
            report = run_single_gate_preflight_for_recipe(recipe, step.path, safety_dir)
            print(format_single_gate_preflight_report(report))
            print()
            if not report.ok:
                ok = False
        else:
            batch = load_batch(step.path)
            for entry in resolve_batch_entries(batch, step.path):
                print(f"Preflight for scheme step {step.label} / batch entry {entry.label}: {entry.recipe_path}")
                report = run_preflight(entry.recipe_path, safety_dir)
                print(format_preflight_report(report))
                print()
                if not report.ok:
                    ok = False
    return ok


def run_scheme_drain_iv_step(args: argparse.Namespace, step) -> dict:
    recipe = load_scheme_step_recipe(step)
    safety = load_named_safety_preset(recipe.safety_preset, args.safety_dir)
    smu = build_fake_smu(args.fake_resistance_ohm, args.fake_noise_std_a) if args.dry_run else Keithley2450(
        recipe.instrument.address,
        recipe.instrument.timeout_ms,
    )
    return execute_recipe_measurement(
        recipe_path=step.path,
        recipe=recipe,
        safety=safety,
        smu=smu,
        plot=args.plot,
        report=args.report,
        summary=args.summary,
        progress=args.progress,
        index_path=args.index_path,
        progress_prefix=f"[{step.label}]",
    )


def run_scheme_single_gate_step(args: argparse.Namespace, step) -> dict:
    recipe = load_scheme_step_single_gate_recipe(step)
    safety = load_named_safety_preset(recipe.safety_preset, args.safety_dir)
    if args.dry_run:
        drain_smu, gate_smu = build_coupled_fake_smus(
            args.fake_channel_resistance_ohm,
            args.fake_gate_leak_resistance_ohm,
            args.fake_gate_modulation_per_v,
            args.fake_noise_std_a,
        )
    else:
        drain_smu = Keithley2450(recipe.drain_instrument.address, recipe.drain_instrument.timeout_ms)
        gate_smu = Keithley2450(recipe.gate_instrument.address, recipe.gate_instrument.timeout_ms)
    progress_callback = (lambda point, total: print_single_gate_progress(point, total)) if args.progress else None
    metadata = run_single_gate_sweep(
        recipe,
        safety,
        drain_smu,
        gate_smu,
        recipe_path=step.path,
        progress_callback=progress_callback,
    )
    run_dir = Path(metadata["run_dir"])
    print(f"CSV: {metadata['csv_path']}")
    print(f"Metadata: {metadata['metadata_path']}")
    print(f"Metadata completed: {metadata['completed']}")
    if args.gate_stats and metadata["points_written"] > 0:
        stats_path = write_single_gate_stats_csv(run_dir)
        update_metadata_file(Path(metadata["metadata_path"]), {"single_gate_stats_path": str(stats_path)})
        print(f"Single-gate stats: {stats_path}")
    if args.plot and metadata["points_written"] > 0:
        plot_path = write_single_gate_heatmap_svg(run_dir)
        update_metadata_file(Path(metadata["metadata_path"]), {"single_gate_heatmap_path": str(plot_path)})
        print(f"Single-gate heatmap: {plot_path}")
    if args.report and metadata["points_written"] > 0:
        report_path = write_single_gate_report(run_dir)
        update_metadata_file(Path(metadata["metadata_path"]), {"single_gate_report_path": str(report_path)})
        print(f"Single-gate report: {report_path}")
    indexed_metadata = read_metadata_file(Path(metadata["metadata_path"]))
    written_index_path = append_run_index(indexed_metadata, args.index_path)
    print(f"Index: {written_index_path}")
    if args.summary and metadata["points_written"] > 0:
        print()
        print(format_single_gate_summary(summarize_single_gate_run(run_dir)))
    return read_metadata_file(Path(metadata["metadata_path"]))


def run_scheme_batch_step(args: argparse.Namespace, step, scheme_dir: Path) -> tuple[int, Path | None]:
    batch = load_batch(step.path)
    entries = resolve_batch_entries(batch, step.path)
    batch_dir, batch_summary = create_batch_summary(
        batch,
        step.path,
        args.dry_run,
        scheme_dir / "batches",
    )
    print(f"Nested batch summary directory: {batch_dir}")
    worst_exit_code = 0
    summary_path: Path | None = None
    try:
        for number, entry in enumerate(entries, start=1):
            print()
            print(f"=== Nested batch {step.label} {number}/{len(entries)}: {entry.label} ===")
            recipe = load_recipe(entry.recipe_path)
            safety = load_named_safety_preset(recipe.safety_preset, args.safety_dir)
            smu = build_fake_smu(args.fake_resistance_ohm, args.fake_noise_std_a) if args.dry_run else Keithley2450(
                recipe.instrument.address,
                recipe.instrument.timeout_ms,
            )
            metadata = execute_recipe_measurement(
                recipe_path=entry.recipe_path,
                recipe=recipe,
                safety=safety,
                smu=smu,
                plot=args.plot,
                report=args.report,
                summary=args.summary,
                progress=args.progress,
                index_path=args.index_path,
                progress_prefix=f"[{step.label}:{entry.label}]",
            )
            batch_summary["runs"].append(
                {
                    "label": entry.label,
                    "base_label": entry.base_label,
                    "repeat_index": entry.repeat_index,
                    "repeat_count": entry.repeat_count,
                    "recipe_path": str(entry.recipe_path),
                    "completed": metadata.get("completed"),
                    "interrupted": metadata.get("interrupted"),
                    "error_type": metadata.get("error_type"),
                    "error_message": metadata.get("error_message"),
                    "points_written": metadata.get("points_written"),
                    "run_dir": metadata.get("run_dir"),
                    "metadata_path": metadata.get("metadata_path"),
                    "csv_path": metadata.get("csv_path"),
                    "plot_path": metadata.get("plot_path"),
                    "report_path": metadata.get("report_path"),
                    "quality": metadata.get("quality"),
                }
            )
            exit_code = exit_code_for_metadata(metadata)
            worst_exit_code = max(worst_exit_code, exit_code)
            if exit_code != 0 and batch.stop_on_error:
                print("Nested batch stopped after failed recipe.")
                break
            if entry.interval_s > 0 and number < len(entries):
                print(f"Waiting {entry.interval_s:.6g} s before next nested batch entry...")
                time.sleep(entry.interval_s)
    finally:
        summary_path = finish_batch_summary(batch_dir, batch_summary)
        batch_quality = evaluate_batch_quality(summary_path)
        update_batch_summary_quality(summary_path, batch_quality)
        print(format_batch_quality(batch_quality))
        if batch_quality.get("status") == "FAIL":
            worst_exit_code = max(worst_exit_code, 2)
        if args.batch_csv:
            write_batch_runs_csv(summary_path)
        if args.batch_points:
            write_batch_points_csv(summary_path)
        if args.batch_stats:
            write_batch_stats_csv(summary_path)
        if args.batch_report:
            write_batch_report(summary_path)
    return worst_exit_code, summary_path


def write_scheme_steps_csv(summary_path: Path) -> Path:
    import csv

    data = read_metadata_file(summary_path)
    output = summary_path.with_name("scheme_steps.csv")
    fieldnames = [
        "index",
        "label",
        "type",
        "repeat_index",
        "repeat_count",
        "matrix_label",
        "matrix_index",
        "matrix_count",
        "completed",
        "error_type",
        "run_dir",
        "metadata_path",
        "batch_summary_path",
        "path",
        "overrides",
    ]
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for index, step in enumerate(data.get("steps") or [], start=1):
            writer.writerow({"index": index, **{key: step.get(key) for key in fieldnames if key != "index"}})
    return output


def command_preflight(args: argparse.Namespace) -> int:
    report = run_preflight(args.recipe, args.safety_dir)
    print(format_preflight_report(report))
    return 0 if report.ok else 2


def command_new_recipe(args: argparse.Namespace) -> int:
    path = write_recipe_template(
        args.output,
        mode=args.mode,
        measurement_name=args.measurement_name,
        address=args.address,
        sample_id=args.sample_id,
        device_id=args.device_id,
        cooldown_id=args.cooldown_id,
        contact_geometry=args.contact_geometry,
        contact_notes=args.contact_notes,
        lab_notebook_ref=args.lab_notebook_ref,
        operator=args.operator,
        overwrite=args.overwrite,
    )
    print(f"Recipe: {path}")
    print(format_validation_report(validate_recipe_file(path)))
    return 0


def command_new_batch(args: argparse.Namespace) -> int:
    path = write_batch_template(
        args.output,
        kind=args.kind,
        name=args.name,
        recipe=args.recipe,
        repeat=args.repeat,
        interval_s=args.interval_s,
        overwrite=args.overwrite,
    )
    print(f"Batch: {path}")
    batch = load_batch(path)
    print(format_batch_plan(batch, path))
    return 0


def command_new_scheme(args: argparse.Namespace) -> int:
    path = write_scheme_template(
        args.output,
        kind=args.kind,
        name=args.name,
        recipe=args.recipe,
        batch=args.batch,
        repeat=args.repeat,
        interval_s=args.interval_s,
        overwrite=args.overwrite,
    )
    print(f"Wrote scheme template: {path}")
    scheme = load_scheme(path)
    print(format_scheme_plan(scheme, path))
    return 0


def command_summarize(args: argparse.Namespace) -> int:
    metadata = read_metadata_file(args.run_dir / "metadata.json")
    handler = handler_for_metadata(metadata)
    print(handler.format_summary(handler.summarize(args.run_dir)))
    return 0


def command_inspect_run(args: argparse.Namespace) -> int:
    print(inspect_run(args.run_dir))
    return 0


def command_plot(args: argparse.Namespace) -> int:
    metadata = read_metadata_file(args.run_dir / "metadata.json")
    output_path = handler_for_metadata(metadata).write_plot(args.run_dir, args.output)
    print(f"Plot: {output_path}")
    return 0


def command_report(args: argparse.Namespace) -> int:
    metadata = read_metadata_file(args.run_dir / "metadata.json")
    output_path = handler_for_metadata(metadata).write_report(args.run_dir, args.output)
    print(f"Report: {output_path}")
    return 0


def command_single_gate_summary(args: argparse.Namespace) -> int:
    print(format_single_gate_summary(summarize_single_gate_run(args.run_dir)))
    return 0


def command_single_gate_plot(args: argparse.Namespace) -> int:
    output_path = write_single_gate_heatmap_svg(args.run_dir, args.output)
    print(f"Single-gate heatmap: {output_path}")
    return 0


def command_single_gate_report(args: argparse.Namespace) -> int:
    output_path = write_single_gate_report(args.run_dir, args.output)
    print(f"Single-gate report: {output_path}")
    return 0


def command_single_gate_stats(args: argparse.Namespace) -> int:
    output_path = write_single_gate_stats_csv(args.run_dir, args.output)
    print(f"Single-gate stats: {output_path}")
    return 0


def command_check_run(args: argparse.Namespace) -> int:
    quality_report = evaluate_run_quality(args.run_dir)
    print(format_quality_report(quality_report))
    return 0 if quality_report.status in {"PASS", "SKIP"} else 2


def command_batch_report(args: argparse.Namespace) -> int:
    output_path = write_batch_report(args.batch_summary_or_dir, args.output)
    print(format_batch_review(summarize_batch(args.batch_summary_or_dir)))
    print(f"Batch report: {output_path}")
    return 0


def command_batch_plot(args: argparse.Namespace) -> int:
    output_path = write_batch_overlay_svg(args.batch_summary_or_dir, args.output)
    print(f"Batch plot: {output_path}")
    return 0


def command_batch_csv(args: argparse.Namespace) -> int:
    output_path = write_batch_runs_csv(args.batch_summary_or_dir, args.output)
    print(f"Batch CSV: {output_path}")
    return 0


def command_batch_points(args: argparse.Namespace) -> int:
    output_path = write_batch_points_csv(args.batch_summary_or_dir, args.output)
    print(f"Batch points: {output_path}")
    return 0


def command_batch_stats(args: argparse.Namespace) -> int:
    output_path = write_batch_stats_csv(args.batch_summary_or_dir, args.output)
    print(f"Batch stats: {output_path}")
    return 0


def command_scheme_report(args: argparse.Namespace) -> int:
    quality = evaluate_scheme_quality(args.scheme_summary_or_dir)
    update_scheme_summary_quality(args.scheme_summary_or_dir, quality)
    output_path = write_scheme_review_report(args.scheme_summary_or_dir, args.output)
    print(format_scheme_quality(quality))
    print(f"Scheme report: {output_path}")
    return 0


def command_scheme_plot(args: argparse.Namespace) -> int:
    output_path = write_scheme_overlay_svg(args.scheme_summary_or_dir, args.output)
    print(f"Scheme plot: {output_path}")
    return 0


def command_scheme_runs(args: argparse.Namespace) -> int:
    output_path = write_scheme_runs_csv(args.scheme_summary_or_dir, args.output)
    print(f"Scheme runs CSV: {output_path}")
    return 0


def command_scheme_points(args: argparse.Namespace) -> int:
    output_path = write_scheme_points_csv(args.scheme_summary_or_dir, args.output)
    print(f"Scheme points CSV: {output_path}")
    return 0


def command_scheme_stats(args: argparse.Namespace) -> int:
    output_path = write_scheme_stats_csv(args.scheme_summary_or_dir, args.output)
    print(f"Scheme stats CSV: {output_path}")
    return 0


def command_campaign(args: argparse.Namespace) -> int:
    completed = None
    if args.completed_only and args.incomplete_only:
        print("--completed-only and --incomplete-only cannot be used together.", file=sys.stderr)
        return 2
    if args.completed_only:
        completed = True
    if args.incomplete_only:
        completed = False
    filters = CampaignFilters(
        sample_id=args.sample,
        device_id=args.device,
        tag=args.tag,
        quality_status=args.qc_status,
        completed=completed,
        failed_only=args.failed_only,
        measurement_contains=args.measurement_contains,
        min_resistance_ohm=args.min_resistance_ohm,
        max_resistance_ohm=args.max_resistance_ohm,
    )
    paths = create_campaign(
        name=args.name,
        raw_dir=args.raw_dir,
        batch_dir=args.batch_dir,
        scheme_dir=args.scheme_dir,
        output_dir=args.output_dir,
        filters=filters,
        analytics=args.analytics,
    )
    print(f"Campaign directory: {paths.campaign_dir}")
    print(f"Campaign manifest: {paths.manifest_path}")
    print(f"Campaign runs CSV: {paths.runs_csv_path}")
    print(f"Campaign report: {paths.report_path}")
    if paths.stats_csv_path is not None:
        print(f"Campaign stats CSV: {paths.stats_csv_path}")
    if paths.histogram_path is not None:
        print(f"Campaign histogram: {paths.histogram_path}")
    return 0


def command_campaign_report(args: argparse.Namespace) -> int:
    output_path = write_campaign_review_report(args.campaign_manifest_or_dir, args.output)
    print(f"Campaign report: {output_path}")
    return 0


def command_campaign_stats(args: argparse.Namespace) -> int:
    output_path = write_campaign_stats_csv(args.campaign_manifest_or_dir, args.output)
    print(f"Campaign stats CSV: {output_path}")
    return 0


def command_campaign_histogram(args: argparse.Namespace) -> int:
    output_path = write_campaign_resistance_histogram_svg(args.campaign_manifest_or_dir, args.output, args.bins)
    print(f"Campaign histogram: {output_path}")
    return 0


def command_campaign_bundle(args: argparse.Namespace) -> int:
    paths = export_campaign_bundle(
        args.campaign_manifest_or_dir,
        output_dir=args.output_dir,
        include_points=not args.no_points,
        include_plots=not args.no_plots,
        include_reports=not args.no_reports,
    )
    print(f"Campaign bundle directory: {paths.bundle_dir}")
    print(f"Campaign bundle manifest: {paths.bundle_manifest_path}")
    print(f"Campaign bundle ZIP: {paths.zip_path}")
    return 0


def command_feedback_bundle(args: argparse.Namespace) -> int:
    paths = create_feedback_bundle(
        args.run_dir,
        output_dir=args.output_dir,
        include_points=not args.no_points,
        include_plots=not args.no_plots,
        include_reports=not args.no_reports,
        extra_files=args.extra_file,
    )
    print(f"Feedback bundle directory: {paths.bundle_dir}")
    print(f"Feedback bundle manifest: {paths.manifest_path}")
    print(f"Feedback bundle ZIP: {paths.zip_path}")
    return 0


def command_list_runs(args: argparse.Namespace) -> int:
    records = read_run_index(args.index_path)
    completed = True if args.completed else None
    interrupted = True if args.interrupted else None
    records = filter_run_index(
        records,
        sample_id=args.sample,
        device_id=args.device,
        tag=args.tag,
        measurement_type=args.measurement_type,
        completed=completed,
        failed=args.failed,
        interrupted=interrupted,
    )
    print(format_run_index(records, limit=args.limit))
    return 0


def command_rebuild_index(args: argparse.Namespace) -> int:
    index_path, count = rebuild_run_index(args.raw_dir, args.index_path)
    print(f"Rebuilt index: {index_path}")
    print(f"Runs indexed: {count}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "list-resources":
        return command_list_resources()
    if args.command == "doctor":
        return command_doctor(args)
    if args.command == "identify":
        return command_identify(args)
    if args.command == "probe":
        return command_probe(args)
    if args.command == "run":
        return command_run(args)
    if args.command == "single-gate-plan":
        return command_single_gate_plan(args)
    if args.command == "single-gate-preflight":
        return command_single_gate_preflight(args)
    if args.command == "single-gate":
        return command_single_gate(args)
    if args.command == "dual-gate-plan":
        return command_dual_gate_plan(args)
    if args.command == "dual-gate":
        return command_dual_gate(args)
    if args.command == "dual-gate-lockin-plan":
        return command_dual_gate_lockin_plan(args)
    if args.command == "dual-gate-lockin-preflight":
        return command_dual_gate_lockin_preflight(args)
    if args.command == "dual-gate-lockin-smoke":
        return command_dual_gate_lockin_smoke(args)
    if args.command == "dual-gate-lockin-active-smoke":
        return command_dual_gate_lockin_active_smoke(args)
    if args.command == "dual-gate-lockin":
        return command_dual_gate_lockin(args)
    if args.command == "ac-lockin-plan":
        return command_ac_lockin_plan(args)
    if args.command == "ac-lockin-preflight":
        return command_ac_lockin_preflight(args)
    if args.command == "ac-lockin":
        return command_ac_lockin(args)
    if args.command == "pulse-plan":
        return command_pulse_plan(args)
    if args.command == "pulse":
        return command_pulse(args)
    if args.command == "validate":
        return command_validate(args)
    if args.command == "plan":
        return command_plan(args)
    if args.command == "scheme-plan":
        return command_scheme_plan(args)
    if args.command == "scheme":
        return command_scheme(args)
    if args.command == "batch":
        return command_batch(args)
    if args.command == "preflight":
        return command_preflight(args)
    if args.command == "new-recipe":
        return command_new_recipe(args)
    if args.command == "new-batch":
        return command_new_batch(args)
    if args.command == "new-scheme":
        return command_new_scheme(args)
    if args.command == "summarize":
        return command_summarize(args)
    if args.command == "inspect-run":
        return command_inspect_run(args)
    if args.command == "plot":
        return command_plot(args)
    if args.command == "report":
        return command_report(args)
    if args.command == "single-gate-summary":
        return command_single_gate_summary(args)
    if args.command == "single-gate-plot":
        return command_single_gate_plot(args)
    if args.command == "single-gate-report":
        return command_single_gate_report(args)
    if args.command == "single-gate-stats":
        return command_single_gate_stats(args)
    if args.command == "check-run":
        return command_check_run(args)
    if args.command == "batch-report":
        return command_batch_report(args)
    if args.command == "batch-plot":
        return command_batch_plot(args)
    if args.command == "batch-csv":
        return command_batch_csv(args)
    if args.command == "batch-points":
        return command_batch_points(args)
    if args.command == "batch-stats":
        return command_batch_stats(args)
    if args.command == "scheme-report":
        return command_scheme_report(args)
    if args.command == "scheme-plot":
        return command_scheme_plot(args)
    if args.command == "scheme-runs":
        return command_scheme_runs(args)
    if args.command == "scheme-points":
        return command_scheme_points(args)
    if args.command == "scheme-stats":
        return command_scheme_stats(args)
    if args.command == "campaign":
        return command_campaign(args)
    if args.command == "campaign-report":
        return command_campaign_report(args)
    if args.command == "campaign-stats":
        return command_campaign_stats(args)
    if args.command == "campaign-histogram":
        return command_campaign_histogram(args)
    if args.command == "campaign-bundle":
        return command_campaign_bundle(args)
    if args.command == "feedback-bundle":
        return command_feedback_bundle(args)
    if args.command == "list-runs":
        return command_list_runs(args)
    if args.command == "rebuild-index":
        return command_rebuild_index(args)
    parser.error(f"Unknown command {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
