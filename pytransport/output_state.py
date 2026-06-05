"""Output state metadata helpers for hardware runners."""

from __future__ import annotations

from typing import Any


def initialize_output_state(metadata: dict[str, Any], roles: list[str]) -> None:
    metadata["output_state"] = {
        role: {
            "output_on_attempted": False,
            "enabled": False,
            "output_on_error": None,
            "output_off_attempted": False,
            "off_after_run": False,
            "output_off_error": None,
        }
        for role in roles
    }


def output_on_with_state(role: str, smu: Any, metadata: dict[str, Any]) -> None:
    state = _role_state(metadata, role)
    state["output_on_attempted"] = True
    try:
        smu.output_on()
    except Exception as exc:
        state["output_on_error"] = f"{type(exc).__name__}: {exc}"
        raise
    state["enabled"] = True


def output_off_with_state(role: str, smu: Any, metadata: dict[str, Any]) -> None:
    state = _role_state(metadata, role)
    state["output_off_attempted"] = True
    try:
        smu.output_off()
    except Exception as exc:
        state["output_off_error"] = f"{type(exc).__name__}: {exc}"
        return
    state["enabled"] = False
    state["off_after_run"] = True


def all_outputs_off_after_run(metadata: dict[str, Any], roles: list[str] | None = None) -> bool:
    output_state = metadata.get("output_state") or {}
    active_roles = roles or list(output_state)
    return all((output_state.get(role) or {}).get("off_after_run") is True for role in active_roles)


def any_output_enabled(metadata: dict[str, Any]) -> bool:
    return any((state or {}).get("enabled") is True for state in (metadata.get("output_state") or {}).values())


def _role_state(metadata: dict[str, Any], role: str) -> dict[str, Any]:
    output_state = metadata.setdefault("output_state", {})
    return output_state.setdefault(
        role,
        {
            "output_on_attempted": False,
            "enabled": False,
            "output_on_error": None,
            "output_off_attempted": False,
            "off_after_run": False,
            "output_off_error": None,
        },
    )
