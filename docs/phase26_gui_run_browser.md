# Phase 26 - GUI Run Browser

This phase makes the GUI useful after a measurement session by reading the
existing run index.

## Implemented

- Added GUI service helpers to list indexed runs from `data/run_index.jsonl`.
- Added GUI service helper to load a saved run and format its summary, quality,
  metadata, and artifact paths.
- Added `Refresh Runs` and `Load Selected` buttons.
- Expanded the `Runs` table to show:
  - started time
  - measurement type
  - measurement name
  - completion state
  - point count
  - run folder
- Selecting a saved run and loading it fills the Summary, Metadata, and Report
  tabs and enables artifact-open buttons.
- Made run-index reading tolerant of UTF-8 BOMs created by some Windows text
  editing commands.

## Workflow

```powershell
ptm-gui
```

Then:

1. Open the `Runs` tab.
2. Click `Refresh Runs`.
3. Select a row.
4. Click `Load Selected`.
5. Use `Run Folder`, `Plot`, or `Report` to open artifacts.

## Notes

The run browser reads the same append-only index used by `ptm list-runs`.
It does not scan the full `data/raw` directory by itself. If the index is
missing or stale, run:

```powershell
ptm rebuild-index
```
