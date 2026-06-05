# Phase 53: GUI Scheme Comparison

## Goal

Let the GUI compare multiple saved scheme results without opening CSV files by
hand.

This builds on the saved scheme browser. A user can select one or more saved
scheme rows and inspect per-scheme/per-step stability statistics in the GUI.

## What Changed

- Added `GuiSchemeComparison`.
- Added `compare_gui_schemes()`.
- Added `Compare Selected` in the `Schemes` workspace.
- Added a `Compare` tab containing:
  - a short text summary, and
  - a sortable comparison table.
- Comparison rows include:
  - scheme name,
  - step label,
  - started time,
  - completion status,
  - scheme QC status,
  - dry-run flag,
  - run count,
  - completed run count,
  - QC pass/fail counts,
  - mean fitted resistance,
  - resistance standard deviation,
  - relative standard deviation,
  - min/max fitted resistance.

## Design Notes

The comparison service reuses `scheme_stats_rows()` from `scheme_review.py`.
That keeps the GUI comparison numerically consistent with CLI scheme stats
exports.

The GUI only renders comparison rows. It does not recompute fitted resistance or
parse point CSV files directly.

Duplicate selected scheme paths are ignored by the service. Missing paths are
also skipped, which makes stale selections less disruptive during GUI review.

## Current Scope

Supported:

- Comparing one or more selected saved schemes.
- Recomputing stats from `scheme_summary.json` and linked run `points.csv`.
- Sorting comparison columns.

Not yet included:

- In-app scheme overlay plot preview.
- Side-by-side graphical comparison.
- Exporting the GUI comparison table as CSV.
- Multi-column filtering in the saved scheme table.

## User Checklist

- Launch `ptm-gui`.
- Open `Schemes`.
- Click `Refresh Saved`.
- Select one or more rows in `Saved`.
- Click `Compare Selected`.
- Open `Compare`.
- Confirm the text summary lists the selected schemes.
- Confirm the comparison table has one row per scheme/step.
- Sort by `Mean R` or `Rel Std %` and confirm rows reorder.
