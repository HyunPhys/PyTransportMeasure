# Phase 25bk: Hall-Suite Next-Scan Proposal

## What Changed

- Added `ptm dual-gate-lockin-hall-suite-next-scan-proposal`.
- The command consumes an accepted Hall-suite analysis review JSON or its
  parent `hall_analysis` directory.
- It writes:
  - `hall_suite_next_scan_proposal.md`
  - `hall_suite_next_scan_proposal.json`
- It intentionally does not write hardware recipes.

## Why

The program is moving toward Hall-bar graphene dual-gate workflows. After a
suite is measured, ingested, analyzed, and reviewed, the next measurement should
be chosen from the data while preserving the measurement conditions that made
the previous scan comparable. This phase adds a decision artifact between
analysis and recipe generation.

## Command

```powershell
ptm dual-gate-lockin-hall-suite-next-scan-proposal data\hall_packages\<sample_lab_package>\hall_analysis
```

The command refuses to run when `hall_suite_analysis_review.json` is not
accepted for next-scan decision.

## Proposal Policy

- If carrier density changes sign, propose refining the gate grid near the
  lowest-density region.
- If carrier density keeps one sign, propose a modest gate-window broadening.
- If finite density is missing, propose repeating/debugging instead of
  broadening.
- Always set `hardware_recipe_written: false`.
- Always set `accepted_for_recipe_generation: false`.
- Always set `requires_lab_approval: true`.

## Measurement Settings

The proposal attempts to read the package manifest and copied recipes tied to
the analyzed run. It carries forward:

- Keithley 2450 NPLC
- voltage range
- current range
- current compliance
- source delay
- gate settle time
- SR860 frequency, excitation amplitude, sensitivity index, and time constant

Do not change these settings between comparable scans unless the lab notebook
explicitly records why the speed/noise or safety tradeoff changed.

## Lab Checklist

- [ ] Run suite review and confirm it is accepted.
- [ ] Run `ptm dual-gate-lockin-hall-suite-next-scan-proposal`.
- [ ] Confirm the proposal did not write hardware recipes.
- [ ] Confirm the proposed gate range and point counts make physical sense.
- [ ] Confirm preserved NPLC/range/compliance/SR860 settings match the intended
      next scan.
- [ ] Approve changes in the lab notebook before generating adjusted recipes.

## Verification

- `python -m pytest tests\test_hall_suite_template.py -q`
- `python -m pytransport.cli dual-gate-lockin-hall-suite-next-scan-proposal --help`
