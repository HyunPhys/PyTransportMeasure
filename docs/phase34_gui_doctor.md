# Phase 34 - GUI Lab Doctor

This phase adds lab-laptop diagnostics to the PySide6 GUI.

## Implemented

- Added a `Doctor` button.
- Added a `Doctor` tab.
- The GUI doctor reports Python/platform/PyVISA state, VISA resources, and probe
  results.
- For Drain I-V recipes, the doctor automatically reads the current YAML editor
  Keithley address and timeout.
- For other methods, the doctor runs an environment/resource check without a
  method-specific probe.
- The doctor runs in a worker thread so the GUI stays responsive during VISA
  access.

## Workflow

```powershell
ptm-gui
```

Then:

1. Select `Drain I-V`.
2. Confirm the YAML editor contains the intended Keithley address.
3. Click `Doctor`.
4. Open the `Doctor` tab.
5. Confirm `OK: True`, `Address found: True`, and Keithley probe fields.

## Intended Use

Use GUI Doctor before `Preflight` or `Hardware Run` on the lab laptop. If Doctor
fails, fix the laptop/VISA/Keithley connection before running a recipe.
