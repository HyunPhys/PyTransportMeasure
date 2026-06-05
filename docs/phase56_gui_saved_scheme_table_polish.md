# Phase 56: GUI Saved Scheme Table Polish

## Goal

Make the saved scheme browser more comfortable for repeated lab use.

This phase keeps the last source folders, improves table readability, and makes
saved scheme filters quicker to apply.

## What Changed

- Added `GuiState`.
- Added `load_gui_state()` and `save_gui_state()`.
- The GUI stores source folders in `data/gui_state.json`:
  - run source folder,
  - scheme source folder.
- Source folders are saved when:
  - a source folder is selected,
  - runs or schemes are refreshed,
  - the GUI closes.
- Saved scheme and comparison tables now get explicit initial column widths.
- Pressing Enter in the saved scheme name filter refreshes the table.

## Design Notes

The state file is intentionally small and GUI-specific. It does not affect
measurement recipes, metadata, or hardware behavior.

The JSON helpers live in `pytransport.gui_services`, while the PySide GUI only
reads values into widgets and saves the current widget values.

If `data/gui_state.json` is missing or invalid, the GUI falls back to:

- `data/raw`
- `data/schemes`

## User Checklist

- Launch `ptm-gui`.
- Open `Analysis` and choose a run source folder.
- Open `Schemes` and choose a saved scheme source folder.
- Close and relaunch `ptm-gui`.
- Confirm the source folder fields remember the previous values.
- Open `Schemes`.
- Confirm `Saved` and `Compare` columns are readable without manual resizing.
- Type a scheme-name filter and press Enter.
- Confirm `Saved` refreshes.
