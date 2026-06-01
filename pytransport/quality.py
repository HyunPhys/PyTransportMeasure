"""Post-run quality checks for measurement smoke tests."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .inspect import read_run_metadata
from .method_registry import handler_for_metadata


@dataclass(frozen=True)
class QualityCheckResult:
    name: str
    passed: bool
    message: str


@dataclass(frozen=True)
class QualityReport:
    status: str
    results: list[QualityCheckResult]


def evaluate_run_quality(run_dir: str | Path) -> QualityReport:
    path = Path(run_dir)
    metadata = read_run_metadata(path)
    recipe = metadata.get("recipe") or {}
    checks = recipe.get("checks")
    if not checks:
        return QualityReport(status="SKIP", results=[])

    summary = handler_for_metadata(metadata).summarize(path)
    results: list[QualityCheckResult] = []
    if checks.get("require_completed", True):
        results.append(
            QualityCheckResult(
                name="completed",
                passed=summary.completed is True,
                message=f"completed={summary.completed}",
            )
        )
    min_points = checks.get("min_points")
    if min_points is not None:
        results.append(
            QualityCheckResult(
                name="min_points",
                passed=summary.points >= min_points,
                message=f"points={summary.points}, required>={min_points}",
            )
        )
    resistance_check = checks.get("fitted_resistance_ohm")
    if resistance_check:
        resistance = getattr(summary, "fitted_resistance_ohm", None)
        min_ohm = resistance_check.get("min_ohm")
        max_ohm = resistance_check.get("max_ohm")
        passed = resistance is not None
        if min_ohm is not None and resistance is not None:
            passed = passed and resistance >= min_ohm
        if max_ohm is not None and resistance is not None:
            passed = passed and resistance <= max_ohm
        results.append(
            QualityCheckResult(
                name="fitted_resistance_ohm",
                passed=passed,
                message=(
                    f"fitted={format_float(resistance)} ohm, "
                    f"min={format_float(min_ohm)} ohm, max={format_float(max_ohm)} ohm"
                ),
            )
        )
    if not results:
        return QualityReport(status="SKIP", results=[])
    return QualityReport(status="PASS" if all(result.passed for result in results) else "FAIL", results=results)


def quality_report_to_dict(report: QualityReport) -> dict[str, Any]:
    return {
        "status": report.status,
        "results": [
            {"name": result.name, "passed": result.passed, "message": result.message}
            for result in report.results
        ],
    }


def format_quality_report(report: QualityReport) -> str:
    lines = [f"Quality: {report.status}"]
    for result in report.results:
        mark = "PASS" if result.passed else "FAIL"
        lines.append(f"- {result.name}: {mark} ({result.message})")
    return "\n".join(lines)


def format_float(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.6g}"
