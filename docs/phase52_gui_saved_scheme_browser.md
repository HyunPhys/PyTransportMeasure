# Phase 52: GUI Saved Scheme Browser

## Goal

Let the desktop GUI browse scheme results that were already saved under
`data/schemes` or another selected source folder.

This makes scheme review a repeatable GUI workflow instead of something that
only works immediately after a dry-run.

## What Changed

- Added `list_gui_schemes()`.
- Added `load_gui_saved_scheme()`.
- Added a `Saved` table to the GUI `Schemes` workspace.
- Added saved-scheme source folder controls:
  - `Source Folder`
  - `Refresh Saved`
  - `Load Selected`
- Saved scheme rows show:
  - started time,
  - scheme name,
  - completion status,
  - scheme QC status,
  - dry-run flag,
  - step count,
  - expanded run count,
  - scheme folder.
- Loading a saved scheme fills the existing `Result` and `Report` tabs.
- `Scheme Folder` opens the loaded scheme directory.
- `Scheme Report` is enabled only when `scheme_report.md` exists on disk.

## Design Notes

The GUI does not parse scheme folders directly. File scanning and formatting
live in `pytransport.gui_services`, while `pytransport.gui_app` only renders the
records and connects buttons.

The browser reads `scheme_summary.json` files from:

- the selected source folder itself, if it is a scheme folder, and
- one directory level below the selected source folder.

For nested batch steps, the browser reads the linked `batch_summary.json` when
available so the `Runs` column reflects the number of batch runs rather than
counting the batch as a single run.

If a saved scheme has no `scheme_report.md`, the GUI still generates report text
from `scheme_summary.json` for review, but the external report-open button stays
disabled.

## User Checklist

- Launch `ptm-gui`.
- Open `Schemes`.
- Click `Refresh Saved`.
- Confirm saved scheme rows appear in `Saved`.
- Click a row in `Saved`.
- Confirm `Load Selected` becomes enabled.
- Click `Load Selected`.
- Confirm `Result` shows the selected scheme summary.
- Confirm `Report` shows the saved or generated report text.
- Click `Scheme Folder` and confirm the selected scheme folder opens.
- If `scheme_report.md` exists, click `Scheme Report` and confirm it opens.
- Use `Source Folder` to select a different parent folder and repeat refresh.
