# Phase 25 - GUI Recipe Builder Foundation

This phase adds the first recipe-building workflow to the PySide6 GUI.

## Implemented

- Added GUI service helpers for:
  - loading default recipe text by method
  - loading recipe text from disk
  - validating editor YAML against the selected method schema
  - saving validated YAML to a chosen path
- Added GUI tabs:
  - `Recipe YAML`
  - `Validation`
- Added GUI buttons:
  - `Load Editor`
  - `Validate YAML`
  - `Save Recipe`
- Kept plan preview and dry-run execution on saved recipe files so the GUI does
  not create a separate measurement path.
- Added tests for default recipe text validation, save behavior, and schema
  error reporting.

## Current Boundary

This is a YAML editor with schema validation, not a full form generator yet.
That is intentional: it gives users a practical recipe-building loop now while
keeping the measurement runners and recipe schemas as the source of truth.

## Workflow

```powershell
ptm-gui
```

Then:

1. Select the measurement method.
2. Edit the YAML in `Recipe YAML`.
3. Click `Validate YAML`.
4. Click `Save Recipe`.
5. Click `Plan`.
6. Click `Dry Run`.

## Next GUI Work

- Add schema-driven forms for common fields.
- Add a diff view between the loaded recipe and edited YAML.
- Add scheme/batch recipe editing.
- Add guarded hardware controls only after the corresponding CLI hardware path
  is smoke-tested.
