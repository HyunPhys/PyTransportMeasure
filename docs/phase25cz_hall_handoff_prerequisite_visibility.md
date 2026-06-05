# Phase 25cz: Hall Handoff Prerequisite Visibility

## Purpose

Hall packages can now include a four-terminal AC smoke intake prerequisite. This
phase makes that prerequisite visible in the lab handoff summary and workflow
status so the lab notebook can show whether the package is backed by accepted
four-terminal AC smoke evidence.

## What Changed

- `ptm dual-gate-lockin-hall-suite-status` now includes a
  `Four-terminal AC smoke prerequisite` stage.
- `ptm dual-gate-lockin-hall-suite-handoff-summary` now records
  `four_terminal_ac_smoke_prerequisite` in `handoff_summary.json`.
- The handoff markdown includes a dedicated Four-Terminal AC Prerequisite
  section.
- Older packages without the prerequisite remain valid; the prerequisite is
  shown as not attached rather than blocking legacy handoffs.

## Lab Checklist

- [ ] Generate or update the Hall package with
  `--four-terminal-ac-smoke-intake-json`.
- [ ] Run:
  ```powershell
  ptm dual-gate-lockin-hall-suite-status data\hall_packages\<package>
  ```
- [ ] Confirm `Four-terminal AC smoke prerequisite` is PASS when evidence was
  attached.
- [ ] Run:
  ```powershell
  ptm dual-gate-lockin-hall-suite-handoff-summary data\hall_packages\<package> --overwrite
  ```
- [ ] Confirm `handoff_summary.md` reports the prerequisite status and intake
  JSON path.

## NPLC Reminder

The prerequisite summary is not a substitute for checking the Hall-suite gate
Keithley NPLC audits. It confirms the four-terminal AC source-smoke NPLC, while
the package's measurement-condition audits confirm the dual-gate Hall recipe
NPLC/range/compliance conditions.
