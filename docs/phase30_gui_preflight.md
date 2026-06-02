# Phase 30 - GUI Drain I-V Preflight

This phase adds a hardware-readiness preflight step to the PySide6 GUI.

## Implemented

- Added a `Preflight` button for Drain I-V recipes.
- Added a `Preflight` tab for the report.
- GUI preflight uses the current YAML editor contents, including unsaved form
  edits.
- Preflight writes a draft recipe under `data/gui_drafts`, then reuses the
  existing CLI preflight path.
- Preflight checks recipe validation, safety limits, available VISA resources,
  whether the recipe address is present, and Keithley probe results.
- The probe runs in a worker thread so the GUI does not block during VISA access.

## Workflow

```powershell
ptm-gui
```

Then:

1. Select `Drain I-V`.
2. Edit the form or YAML.
3. Click `Apply Form to YAML` if using the form.
4. Click `Preflight`.
5. Open the `Preflight` tab.
6. Confirm `Recipe address found: True` and `Preflight OK: True`.

## Boundary

GUI hardware runs are still intentionally not implemented. This phase prepares
the confirmation/readiness layer before any GUI control can turn instrument
output on.
