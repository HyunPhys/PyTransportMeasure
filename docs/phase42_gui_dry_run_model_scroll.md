# Phase 42: GUI Dry-Run Model Scroll

## Goal

Fix the `Dry-run Model` panel so it remains usable after being expanded in a
small or vertically constrained GUI window.

## Implemented

- Wrapped the dry-run model form in a `QScrollArea`.
- Kept the dry-run model collapsed by default.
- Preserved the form's natural row height so labels and fields do not get
  crushed when the panel is reopened.
- Limited the expanded panel height so it does not steal the whole measurement
  workspace from `Workflow`, `Plan`, `Recipe YAML`, `Progress`, or `Live Plot`.
- Updated GUI tests to assert that the scroll container is the visible collapsed
  target.

## User Checklist

- [ ] Start the GUI with `ptm-gui`.
- [ ] Confirm `Dry-run Model` starts collapsed.
- [ ] Expand `Dry-run Model`.
- [ ] Confirm labels and input fields are readable, not vertically crushed.
- [ ] Resize the window shorter and confirm the dry-run model can be scrolled.
- [ ] Collapse and expand it again; confirm the layout remains readable.
- [ ] Run a dry-run and confirm fake settings are still applied normally.
