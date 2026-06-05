# Phase 47: GUI Recipe Overview

## Goal

Add a method-aware Recipe Overview tab to the desktop GUI so the user can inspect
what the current YAML recipe means before planning or running it.

This is a stepping stone toward the later schema-driven form builder. The
overview uses the shared recipe models and method registry instead of adding
GUI-only parsing logic.

## What Changed

- Added `format_recipe_overview_text()` in `pytransport.gui_services`.
- Added a `Recipe Overview` tab in the Measurement workspace.
- The overview updates when:
  - a default recipe is loaded,
  - YAML is edited,
  - a recipe file is opened,
  - Drain I-V form values are applied back to YAML,
  - YAML validation or Plan is run.
- The overview summarizes:
  - method and measurement name,
  - safety preset,
  - experiment metadata,
  - instrument blocks,
  - sweep, gate sweep, bias sweep, pulse, lock-in, output, and checks blocks.
- Invalid or incomplete YAML shows a compact parse/validation error in the same
  tab instead of blocking the rest of the GUI.

## Design Notes

The overview intentionally lives in `gui_services.py`, which has no PySide6
dependency. That keeps GUI display concerns separate from recipe parsing and
makes the summary reusable by a future schema-driven recipe builder or CLI
inspection command.

The implementation is method-aware through the method registry and recipe
models, but it does not over-specialize per method yet. That is deliberate:
future 4-probe, AC, lock-in, pulse hardware, and multi-instrument methods should
be able to add recipe blocks without rewriting the GUI tab.

## User Checklist

- Start the GUI with `ptm-gui`.
- Confirm the Measurement workspace has a `Recipe Overview` tab.
- Confirm the default Drain I-V recipe shows:
  - method,
  - measurement name,
  - safety preset,
  - experiment fields,
  - instrument address,
  - sweep fields.
- Change the method to `Pulse measurement` and confirm the overview shows
  `Source Instrument`, `Pulse`, and `Pulse Limits`.
- Edit a YAML field such as `measurement_name`; confirm the overview updates.
- Temporarily make the YAML invalid; confirm the overview shows a readable error
  and the app remains usable.

