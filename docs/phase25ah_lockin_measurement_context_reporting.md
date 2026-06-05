# Phase 25ah: Lock-In Measurement-Context Reporting

This phase makes lock-in run artifacts more self-describing, especially for
four-terminal Hall-bar work.

## Scope

Reports and summaries now record the measurement context needed to interpret a
saved run folder:

- measurement geometry,
- SR860 input mode,
- SR860 voltage input selection,
- Hall-bar topology layout,
- lock-in voltage contacts,
- excitation contacts.

The values are derived from the saved recipe snapshot inside `metadata.json`.
This keeps exported run folders readable even when the original recipe file has
changed later.

## Affected Artifacts

- `ac_lockin_report.md` now lists lock-in input mode and voltage input.
- `dual_gate_lockin_report.md` now has a `Measurement Context` section.
- `ptm dual-gate-lockin --summary` output includes geometry and contact labels.

## Lab Checklist

- Confirm four-terminal AC reports show `Lock-in voltage input: a-b`.
- Confirm dual-gate lock-in reports show `Lock-in voltage contacts` and
  `Excitation contacts`.
- Confirm the contact labels match the lab notebook and wirebond map before
  promoting a limited run to a larger scan.
