# Phase 25cw: Four-Terminal AC Guarded Hardware Gate

## Purpose

Four-terminal AC lock-in recipes now have an active hardware path, but the path
is intentionally guarded. A four-terminal AC run can enable a Keithley source
while the SR860 reads a separate differential voltage pair, so accidental
hardware execution is blocked unless the operator explicitly confirms the wiring
review.

## What Changed

- `ptm ac-lockin` now refuses four-terminal AC hardware output by default.
- Active four-terminal AC output requires:
  - `--allow-four-terminal-ac`
  - non-empty `--hardware-approval-note`
  - point count no larger than `--max-hardware-points`
- Successful guarded runs save `hardware_guard` in `metadata.json`, including:
  - measurement geometry
  - contact topology
  - approval note
  - point count and point guard
- Two-terminal AC hardware smoke behavior is unchanged.
- Four-terminal AC dry-runs remain available without hardware approval flags.

## Lab Command

```powershell
ptm ac-lockin configs\recipes\ac_lockin_four_terminal_dry_run.yaml --allow-four-terminal-ac --hardware-approval-note "fixture contacts checked; SR860 A-B verified" --max-hardware-points 3 --yes --progress --summary --plot --report
```

## NPLC Reminder

Keithley 2450 NPLC is a measurement condition. Before active hardware output,
confirm `source_instrument.nplc`, `voltage_range_v`, `current_range_a`, and
`bias_sweep.current_compliance_a` are deliberate and recorded in the lab
notebook. The saved metadata should contain the same values under
`configured_source_smu`.

## Checklist

- [ ] Run `ptm ac-lockin-plan` and confirm contact topology.
- [ ] Run `ptm ac-lockin-preflight` and confirm Keithley/SR860 communication.
- [ ] Run a dry-run and inspect CSV/metadata artifacts.
- [ ] Confirm the command without `--allow-four-terminal-ac` refuses hardware.
- [ ] Keep the first active run at three points or fewer.
- [ ] Confirm `metadata.json.hardware_guard` records the approval note and
  contact topology.
- [ ] Run `ptm ac-lockin-lab-smoke-intake` on the saved run before broadening.
