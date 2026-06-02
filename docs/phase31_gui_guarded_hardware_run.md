# Phase 31 - GUI Guarded Drain I-V Hardware Run

This phase adds a guarded Drain I-V hardware run path to the PySide6 GUI.

## Implemented

- Added a `Hardware Run` button for Drain I-V recipes.
- Hardware runs use the current YAML editor contents, including unsaved form
  edits.
- The GUI shows an explicit confirmation dialog before any hardware output can
  be enabled.
- The confirmation dialog summarizes measurement name, VISA address, terminal,
  sweep span, point count, compliance, and safety preset.
- The worker reruns preflight immediately before constructing the Keithley
  driver and enabling output.
- If preflight fails, the hardware run is blocked before output can be enabled.
- Successful hardware runs reuse the existing Drain I-V runner, artifact
  generation, quality check, run index, and plot/report preview path.

## Workflow

```powershell
ptm-gui
```

Then:

1. Select `Drain I-V`.
2. Edit the form or YAML.
3. Click `Apply Form to YAML` if using the form.
4. Click `Plan`.
5. Click `Preflight` and confirm `Preflight OK: True`.
6. Click `Hardware Run`.
7. Read the confirmation dialog carefully.
8. Click `Yes` only when the wiring, terminal, address, sweep, compliance, and
   safety preset are correct.

## Boundary

This phase supports only Keithley 2450 Drain I-V hardware runs. Single-gate,
AC/lock-in, pulse, and 4-probe GUI hardware paths remain future milestones.
