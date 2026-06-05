"""Formatting helpers for measurement geometry and contact context."""

from __future__ import annotations

from typing import Any


def format_geometry(geometry: dict[str, Any]) -> str:
    method = geometry.get("method") or "two_terminal"
    terminal_count = geometry.get("terminal_count") or 2
    notes = geometry.get("notes")
    text = f"{method}, {terminal_count}-terminal"
    return f"{text}, {notes}" if notes else text


def format_lockin_contact_context(
    geometry: dict[str, Any],
    lockin: dict[str, Any],
    topology: dict[str, Any] | None = None,
) -> list[str]:
    lines = [
        f"Measurement geometry: {format_geometry(geometry)}",
        f"Lock-in input mode: {lockin.get('input_mode') or 'n/a'}",
        f"Lock-in voltage input: {lockin.get('voltage_input') or 'n/a'}",
    ]
    if topology is None:
        return lines
    lockin_contacts = topology.get("lockin_input_contacts") or []
    excitation_contacts = topology.get("excitation_contacts") or []
    lines.extend(
        [
            f"Topology layout: {topology.get('device_layout') or 'n/a'}",
            f"Source/drain contacts: {topology.get('source_contact') or 'n/a'} -> {topology.get('drain_contact') or 'n/a'}",
            f"Lock-in voltage contacts: {format_contact_list(lockin_contacts)}",
            f"Excitation contacts: {format_contact_list(excitation_contacts)}",
            f"Excitation source: {topology.get('excitation_source') or 'n/a'}",
        ]
    )
    return lines


def format_contact_list(contacts: list[Any] | tuple[Any, ...]) -> str:
    return ", ".join(str(contact) for contact in contacts) if contacts else "n/a"
