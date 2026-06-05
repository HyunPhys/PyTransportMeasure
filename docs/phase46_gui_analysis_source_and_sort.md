# Phase 46: GUI Analysis Source Folder, Sorting, And Loaded Row

## Goal

Improve the `Analysis` workspace for shared lab use where different researchers
may keep runs under different folders.

## Implemented

- Added a `Source Folder` control in `Analysis`.
- `Refresh Runs` can now scan a selected folder for `metadata.json` files.
- The selected source may be:
  - a parent folder containing many run folders
  - a single run folder containing `metadata.json`
- Enabled sorting on the Runs table.
- Added sort keys so numeric point counts sort numerically rather than as plain
  strings.
- The currently loaded run row is highlighted in light blue.
- Highlighting survives refresh/sorting when the loaded run is still visible.

## Design Notes

This is analysis-only. It does not change measurement execution, instrument
commands, safety checks, or saved run formats.

The source folder scan reads saved `metadata.json` files and builds the same
compact records used by the run index. This keeps GUI filtering compatible with
CLI-created and GUI-created runs.

## User Checklist

- [ ] Start the GUI with `ptm-gui`.
- [ ] Open `Analysis`.
- [ ] Click `Source Folder` and select a folder containing run folders.
- [ ] Click `Refresh Runs`.
- [ ] Confirm runs from that folder appear.
- [ ] Click column headers such as `Started`, `Points`, `Sample`, or `Status`
  and confirm sorting changes.
- [ ] Select a row and click `Load Selected`.
- [ ] Confirm the loaded row is highlighted in light blue.
- [ ] Change sorting or refresh the same source folder and confirm the loaded
  row remains highlighted if still visible.
- [ ] Select a single run folder as the source and confirm that one run appears.
