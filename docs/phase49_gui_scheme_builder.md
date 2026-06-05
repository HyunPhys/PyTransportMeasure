# Phase 49: GUI Scheme Builder MVP

## Goal

Add a desktop GUI workspace for composing measurement scheme YAML from multiple
recipe or batch steps.

This phase is about workflow structure, not hardware execution. The GUI can
create, edit, validate, preview, and save scheme YAML while reusing the existing
`SchemeRecipe` and `format_scheme_plan()` core.

## What Changed

- Added GUI-independent scheme services:
  - `GuiSchemeStepDraft`
  - `default_scheme_text()`
  - `load_scheme_from_text()`
  - `validate_scheme_text()`
  - `format_scheme_plan_text()`
  - `scheme_builder_from_text()`
  - `scheme_text_from_builder()`
- Added a `Schemes` workspace in the desktop GUI.
- Added a scheme step table with:
  - step type: `drain_iv`, `single_gate`, or `batch`,
  - label,
  - recipe or batch path,
  - enabled flag,
  - repeat count,
  - interval seconds.
- Added GUI actions:
  - `Add Step`
  - `Remove Selected`
  - `Scheme YAML -> Form`
  - `Form -> Scheme YAML`
  - `Check Scheme`
  - `Scheme Plan`
  - `Save Scheme As`
- The generated YAML remains visible and directly editable.
- Scheme validation and plan preview use the same scheme model and path
  resolution as the CLI.

## Current Scope

Supported in the GUI builder:

- Direct Drain I-V recipe steps.
- Single-gate recipe steps.
- Batch steps.
- Repeat and interval fields.
- Enabled/disabled steps.
- Scheme plan preview.
- Save-as workflow.

Not yet included:

- GUI execution of schemes.
- GUI editing of Drain I-V overrides or parameter matrices.
- Rich file pickers per step row.

Those remain future phases because they touch run orchestration and method
override semantics more deeply.

## User Checklist

- Launch `ptm-gui`.
- Open `Schemes`.
- Confirm the default scheme has at least one Drain I-V step and one
  single-gate step.
- Edit the scheme name.
- Edit a step label.
- Click `Form -> Scheme YAML` and confirm `Scheme YAML` updates.
- Click `Check Scheme` and confirm validation passes.
- Click `Scheme Plan` and confirm the expanded plan appears.
- Replace a row with:
  - type `batch`,
  - a batch path such as `../batches/drain_iv_1k_repeat_linear.yaml`.
- Click `Form -> Scheme YAML`, then `Scheme YAML -> Form`, and confirm the row
  round-trips.
- Use `Save Scheme As` only after validation passes.

