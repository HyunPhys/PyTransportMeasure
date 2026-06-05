# Phase 25bj: Hall-Suite Analysis Review

## What Changed

- Added `ptm dual-gate-lockin-hall-suite-review`.
- The command reviews an orchestrated Hall-suite analysis folder without
  touching raw run data or instrument-control code.
- It reads:
  - `hall_suite_analysis_manifest.json`
  - `antisym/hall_antisym.csv`
  - optional `zero_corrected/hall_zero_corrected.csv`
  - `mobility/hall_mobility.csv`
- It writes:
  - `hall_suite_analysis_review.md`
  - `hall_suite_analysis_review.json`

## Why

After a Hall-bar graphene dual-gate suite is measured and analyzed, the lab
still needs a deliberate decision before expanding or shifting the next gate
scan. The review command provides one compact checkpoint for density,
conductivity, and mobility maps, while flagging conditions that need human
inspection before another hardware run.

## Command

```powershell
ptm dual-gate-lockin-hall-suite-review data\hall_packages\<sample_lab_package>\hall_analysis
```

Use `--overwrite` to regenerate the report after re-running analysis or editing
derived artifacts during debugging.

## Automatic Checks

- Required analysis manifest and CSV files exist and are readable.
- Mobility and Hall analysis gate grids match.
- Carrier density contains both positive and negative signs.
- Field-even Hall resistance is larger than the antisymmetrized Hall resistance.
- Zero-field Hall resistance is large compared with finite-field Hall
  resistance.
- Zero-field correction changes the inferred carrier-density sign.
- Mobility magnitude is missing at any gate point.

Warnings do not automatically reject the artifacts. They mean the researcher
should inspect the data before deciding the next scan. Errors make
`accepted_for_next_scan_decision` false and return CLI exit code 2.

## NPLC Reminder

Keithley 2450 NPLC is a measurement condition, not a cosmetic setting. It
controls current integration time in power-line cycles. When comparing Hall
suite scans, keep NPLC fixed unless the lab intentionally changes the
speed/noise tradeoff and records that decision.

## Lab Checklist

- [ ] Run Hall-suite intake and confirm PASS.
- [ ] Run `ptm dual-gate-lockin-hall-suite-analyze`.
- [ ] Run `ptm dual-gate-lockin-hall-suite-review`.
- [ ] Confirm `accepted_for_next_scan_decision: true` in the review JSON.
- [ ] Read every warning in the markdown report before choosing the next gate
      range or spacing.
- [ ] Confirm Keithley NPLC, voltage range, current range, compliance, source
      delay, and SR860 settings were intentional for every underlying run.

## Verification

- `python -m pytest tests\test_hall_suite_template.py -q`
