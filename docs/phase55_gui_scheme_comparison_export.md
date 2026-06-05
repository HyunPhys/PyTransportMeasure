# Phase 55: GUI Scheme Comparison Export

## Goal

Make saved scheme comparison results easier to curate, export, and share.

This phase adds lightweight saved-scheme filters and CSV export for the GUI
comparison table.

## What Changed

- Added filters for saved scheme browsing:
  - scheme name contains,
  - completion status,
  - QC status,
  - dry-run/hardware flag.
- Added `Export CSV` for the most recent scheme comparison.
- Added `write_gui_scheme_comparison_csv()`.
- Comparison CSV output uses a stable field order matching the GUI comparison
  table.

## Design Notes

Filtering and export live in `pytransport.gui_services`. The GUI only collects
filter widget values and renders the resulting records.

The comparison export writes the data produced by `compare_gui_schemes()`, so
the CSV matches what the user inspected in the GUI.

## User Checklist

- Launch `ptm-gui`.
- Open `Schemes`.
- Set one or more saved filters.
- Click `Refresh Saved`.
- Select one or more saved scheme rows.
- Click `Compare Selected`.
- Confirm the `Compare` table updates.
- Click `Export CSV`.
- Confirm the CSV contains scheme name, step label, run counts, QC counts, and
  resistance statistics.
