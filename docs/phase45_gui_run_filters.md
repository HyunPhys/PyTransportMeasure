# Phase 45: GUI Run Filters

## Goal

Make the `Analysis` workspace useful once many runs accumulate by filtering the
run index directly in the GUI.

## Implemented

- Added GUI run filters for:
  - sample
  - device
  - cooldown
  - tag
  - method
  - status
- Expanded the Analysis run table to show:
  - status
  - sample
  - device
  - cooldown
  - lab notebook reference
  - tags
- Added `Clear Filters`.
- Added cooldown filtering to the shared run-index filter helper.
- Kept filtering in the GUI service layer so the GUI does not duplicate index
  logic.

## Design Notes

This phase is analysis-only. It does not change runner behavior, instrument
commands, safety checks, or saved artifact formats.

The status filter is derived from existing metadata:

- `Completed`: `completed: true`
- `Incomplete`: `completed: false`
- `Failed`: `error_type` is present
- `Interrupted`: `interrupted: true`

## User Checklist

- [ ] Start the GUI with `ptm-gui`.
- [ ] Open `Analysis`.
- [ ] Click `Refresh Runs`.
- [ ] Confirm the run table shows sample, device, cooldown, notebook, and tags.
- [ ] Enter a sample filter and click `Refresh Runs`.
- [ ] Enter a cooldown filter and click `Refresh Runs`.
- [ ] Select `Completed`, `Failed`, or `Interrupted` from status and refresh.
- [ ] Click `Clear Filters` and confirm the table returns to the unfiltered
  recent-run view.
- [ ] Select a row and click `Load Selected`; confirm summary/metadata/plot still
  load normally.
