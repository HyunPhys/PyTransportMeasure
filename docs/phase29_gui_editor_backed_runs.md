# Phase 29 - GUI Editor-Backed Plan and Dry-Run

This phase makes the GUI execute the current YAML editor contents instead of
re-reading the recipe path for plan preview and dry-run.

## Implemented

- Added service APIs for plan generation from YAML text.
- Added service APIs for dry-run from YAML text.
- GUI `Plan` now previews the current editor YAML.
- GUI `Dry Run` now runs the current editor YAML.
- Unsaved form or YAML edits can be validated and dry-run without first saving
  a recipe file.
- Dry-runs from editor text write a draft recipe under `data/gui_drafts` so the
  core runner still receives a normal recipe path.

## Workflow

```powershell
ptm-gui
```

Then:

1. Edit `Drain I-V Form`, or edit `Recipe YAML` directly.
2. Click `Apply Form to YAML` if using the form.
3. Click `Plan`.
4. Click `Validate YAML`.
5. Click `Dry Run`.

The recipe path field is still used for loading and saving recipes. It is no
longer required for the current editor draft to be saved before a GUI plan or
dry-run.

## Design Notes

The GUI still does not implement measurement logic. Editor text is validated
through the same Pydantic recipe schemas, written as a draft recipe, and then
passed into the existing runner/review/artifact pipeline. This keeps the GUI
aligned with CLI behavior while allowing fast recipe iteration.
