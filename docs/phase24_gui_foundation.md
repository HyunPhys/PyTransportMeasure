# Phase 24 - PySide6 GUI Foundation

This phase adds the first desktop GUI on top of the existing core API.

## Implemented

- Added optional GUI dependency group: `pip install -e ".[gui]"`.
- Added `ptm-gui` entry point.
- Added `pytransport/gui_services.py` as the GUI-facing service layer with no
  PySide dependency.
- Added `pytransport/gui_app.py` as the PySide6 desktop application.
- Added method selection for:
  - Drain I-V
  - Single-gate sweep
  - AC lock-in sweep
  - Pulse measurement
- Added recipe selection, plan preview, dry-run execution, summary, metadata,
  report preview, and recent run table.
- Added buttons to open the run folder, plot, and report.
- Added tests for GUI service plan dispatch and dry-run artifact generation.

## Current Boundary

The GUI only launches dry-runs in this phase. Hardware-enabling controls remain
CLI-only for now, because first-contact hardware runs still need explicit
terminal, wiring, and preflight review in the lab.

The GUI calls the same recipe, runner, safety, method-registry, quality, and
artifact APIs used by the CLI. It does not duplicate measurement logic.

## Commands

```powershell
pip install -e ".[gui,test]"
ptm-gui
```

Use the GUI to select a method and recipe, preview the plan, run a dry-run, and
open the generated artifacts.

## Next GUI Work

- Add live progress streaming into the GUI log.
- Add guarded hardware run controls after the existing CLI hardware paths are
  smoke-tested.
- Add schema-driven recipe editing. The first YAML validation/save workflow is
  now documented in `docs/phase25_gui_recipe_builder.md`.
- Add scheme/batch launch screens.
- Add artifact browser for older indexed runs.
