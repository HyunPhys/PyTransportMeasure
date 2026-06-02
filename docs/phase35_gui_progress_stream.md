# Phase 35 - GUI Progress Stream

This phase adds point-by-point progress streaming to the PySide6 GUI.

## Implemented

- Added a `Progress` tab.
- Dry-run workers emit formatted progress lines as points are written.
- Guarded Drain I-V hardware workers emit formatted progress lines as points are
  written.
- Progress uses the existing runner `progress_callback` hooks instead of adding
  GUI-specific measurement logic.
- Progress formatting supports Drain I-V, single-gate, AC/lock-in, and pulse
  point objects.

## Workflow

```powershell
ptm-gui
```

Then:

1. Run `Dry Run`, or run a guarded Drain I-V hardware measurement.
2. Open the `Progress` tab.
3. Confirm point lines appear during the run.
4. After completion, inspect `Summary`, `Metadata`, `Plot Preview`, and
   `Report`.

## Design Notes

The GUI still does not own measurement execution. It receives point updates from
the same core runner callbacks used by the CLI progress path. This keeps future
method-specific progress display aligned with the runner layer.
