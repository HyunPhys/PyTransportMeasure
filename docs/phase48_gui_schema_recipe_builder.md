# Phase 48: GUI Schema Recipe Builder MVP

## Goal

Replace the Drain I-V-only GUI form path with a schema-driven recipe form that
works across supported measurement methods.

This is a structural GUI phase. It reduces method-specific GUI code and prepares
the application for future methods such as 4-probe, active SR860 acquisition,
multi-instrument measurements, and richer measurement schemes.

## What Changed

- Added GUI-independent schema form services:
  - `GuiSchemaField`
  - `GuiSchemaSection`
  - `schema_form_from_text()`
  - `schema_form_text_from_values()`
- The GUI `Recipe Form` tab is now generated from the current validated recipe
  model instead of a hand-written Drain I-V-only form.
- The form supports all current GUI methods:
  - Drain I-V
  - Single-gate sweep
  - AC lock-in sweep
  - Pulse measurement
- `YAML -> Form` parses the current editor YAML and rebuilds the method-specific
  form.
- `Form -> YAML` applies edited form values back to the YAML editor, validates
  through the method recipe model, and refreshes the Recipe Overview.
- Optional enum fields preserve blank values as `None`, and empty list fields
  such as tags stay as empty lists instead of invalid `None` values.
- Existing Drain I-V form tests remain covered through the old compatibility
  helpers, while new schema-form tests verify Drain I-V and pulse round trips.

## Design Notes

The dynamic form is intentionally generated in `pytransport.gui_services`, which
has no PySide dependency. The GUI only renders field descriptors. This keeps the
core recipe/schema logic reusable for future GUI builders or CLI inspection
commands.

The MVP handles scalar fields, booleans, enum choices, comma-separated scalar
lists, and simple nested recipe blocks. Complex list-of-object editing remains a
future milestone; advanced recipes can still be edited directly in YAML.

## User Checklist

- Launch the GUI with `ptm-gui`.
- Confirm `Measurement > Recipe Form` exists.
- For `Drain I-V`:
  - click `YAML -> Form`,
  - edit `measurement_name` or `experiment.cooldown_id`,
  - click `Form -> YAML`,
  - confirm `Recipe YAML` updates and `Check YAML` passes.
- Switch to `Pulse measurement`:
  - confirm the form shows `source_instrument`, `pulse`, and `pulse_limits`
    fields,
  - edit `pulse.count`,
  - click `Form -> YAML`,
  - confirm `Recipe YAML` updates and `Check YAML` passes.
- Switch to `AC lock-in sweep` and confirm lock-in fields appear.
- Switch to `Single-gate sweep` and confirm drain/gate instrument and sweep
  fields appear.
- Confirm direct YAML editing still works, and `YAML -> Form` refreshes the form
  from the YAML editor.

