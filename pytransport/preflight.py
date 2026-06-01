"""Preflight checks before a hardware measurement."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .instruments.keithley_2450 import Keithley2450
from .recipes import DrainIVRecipe, load_named_safety_preset, load_recipe
from .validation import RecipeValidationReport, format_validation_report, validate_recipe
from .visa_utils import list_resources


@dataclass(frozen=True)
class PreflightReport:
    validation: RecipeValidationReport
    visa_resources: tuple[str, ...]
    address_found: bool
    probe: dict[str, str] | None
    probe_error: str | None

    @property
    def ok(self) -> bool:
        return self.address_found and self.probe_error is None and self.probe is not None


def run_preflight(
    recipe_path: str | Path,
    safety_dir: str | Path = "configs/safety",
    resource_lister: Callable[[], tuple[str, ...]] = list_resources,
    probe_factory: Callable[[str, int], dict[str, str]] | None = None,
) -> PreflightReport:
    recipe = load_recipe(recipe_path)
    return run_preflight_for_recipe(recipe, recipe_path, safety_dir, resource_lister, probe_factory)


def run_preflight_for_recipe(
    recipe: DrainIVRecipe,
    recipe_path: str | Path,
    safety_dir: str | Path = "configs/safety",
    resource_lister: Callable[[], tuple[str, ...]] = list_resources,
    probe_factory: Callable[[str, int], dict[str, str]] | None = None,
) -> PreflightReport:
    safety = load_named_safety_preset(recipe.safety_preset, safety_dir)
    validation = validate_recipe(recipe, safety, recipe_path)
    resources = resource_lister()
    address_found = recipe.instrument.address in resources
    probe = None
    probe_error = None
    if address_found:
        try:
            if probe_factory is None:
                probe = probe_keithley(recipe.instrument.address, recipe.instrument.timeout_ms)
            else:
                probe = probe_factory(recipe.instrument.address, recipe.instrument.timeout_ms)
        except Exception as exc:
            probe_error = f"{type(exc).__name__}: {exc}"
    return PreflightReport(
        validation=validation,
        visa_resources=resources,
        address_found=address_found,
        probe=probe,
        probe_error=probe_error,
    )


def probe_keithley(address: str, timeout_ms: int) -> dict[str, str]:
    smu = Keithley2450(address, timeout_ms)
    try:
        smu.connect()
        return smu.probe()
    finally:
        smu.close()


def format_preflight_report(report: PreflightReport) -> str:
    lines = [
        "Preflight",
        "",
        format_validation_report(report.validation),
        "",
        "VISA resources:",
    ]
    if report.visa_resources:
        lines.extend(f"- {resource}" for resource in report.visa_resources)
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            f"Recipe address found: {report.address_found}",
            "Probe:",
        ]
    )
    if report.probe is not None:
        lines.extend(f"- {key}: {value}" for key, value in report.probe.items())
    elif report.probe_error is not None:
        lines.append(f"- error: {report.probe_error}")
    else:
        lines.append("- skipped")
    lines.extend(["", f"Preflight OK: {report.ok}"])
    return "\n".join(lines)
