# Phase 54: GUI Scheme Overlay Preview

## Goal

Show a saved scheme overlay inside the GUI without stretching an SVG image.

This responds to the earlier plot distortion issue by rendering saved point data
with the same Qt canvas used for in-app run previews.

## What Changed

- Extended `IvPlotCanvas` to support multiple labeled series.
- Added `scheme_plot_series()`.
- Added `read_gui_iv_points()` as the shared GUI CSV point reader.
- Added an `Overlay` tab to the GUI `Schemes` workspace.
- Loading a saved scheme or finishing a scheme dry-run now refreshes the overlay
  preview automatically when plottable Drain I-V-style runs exist.

## Design Notes

The preview reads saved `points.csv` files linked from `scheme_summary.json`.
It does not embed `scheme_overlay.svg`, so resizing the GUI window does not
distort an image artifact.

The existing `scheme_overlay.svg` export remains useful for reports and
external sharing. The GUI preview is a separate interactive display path.

Single-gate runs are skipped in this overlay preview for now, matching the
existing scheme overlay SVG behavior.

## User Checklist

- Launch `ptm-gui`.
- Open `Schemes`.
- Click `Refresh Saved`.
- Select a saved scheme with Drain I-V-style runs.
- Click `Load Selected`.
- Open `Overlay`.
- Confirm multiple traces are shown when the scheme contains multiple plottable
  runs.
- Resize the window and confirm the plot redraws without image stretching.
