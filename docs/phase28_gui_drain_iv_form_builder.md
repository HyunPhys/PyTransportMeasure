# Phase 28 - GUI Drain I-V Form Builder

This phase adds a structured Drain I-V recipe form to the PySide6 GUI.

## Implemented

- Added a `Drain I-V Form` tab.
- Added form fields for measurement metadata, Keithley address/ranges, sweep
  settings, safety preset, output directory, and basic quality checks.
- Added `Load Form from YAML` to populate the form from the current YAML editor.
- Added `Apply Form to YAML` to validate form values through the existing Drain
  I-V Pydantic recipe schema and replace the YAML editor text.
- Kept YAML editing as the source of truth for advanced or future recipes.
- Kept this phase Drain-I-V-only; other methods continue to use the YAML editor.

## Workflow

```powershell
ptm-gui
```

Then:

1. Select `Drain I-V`.
2. Open `Drain I-V Form`.
3. Edit the common fields such as VISA address, sweep range, points,
   compliance, safety preset, and output directory.
4. Click `Apply Form to YAML`.
5. Open `Recipe YAML` or `Validation` to inspect the generated recipe.
6. Click `Dry Run` before using the saved recipe for hardware.

## Design Notes

The form builder does not implement separate measurement logic. It converts form
values into the same YAML schema used by the CLI, then the GUI dry-run and CLI
hardware paths call the existing core APIs. This keeps future form builders for
single-gate, lock-in, pulse, and 4-probe workflows aligned with the same recipe
and runner layers.

The current form supports `linear_one_way` and `forward_backward` Drain I-V
sweeps. Multi-segment editing remains available through YAML.
