# Phase 25daa: Hall Lab Smoke Return Contract

## Purpose

The Hall lab smoke bundle now describes both sides of the lab handoff: what to
check before hardware output and what artifacts must come back after the
Vxx/+B/-B/0B runs.

## What Changed

- `lab_smoke/lab_smoke_bundle.json` now records:
  - four-terminal AC prerequisite summary
  - expected returned run roles
  - required post-run artifacts
  - post-run intake and lab-return command templates
- `lab_smoke/lab_smoke_checklist.md` now includes:
  - Measurement Prerequisites
  - Post-Run Intake And Return
  - the exact `ptm dual-gate-lockin-hall-suite-intake` command template
  - the exact `ptm dual-gate-lockin-hall-suite-lab-return-manifest` command
    template

## Lab Checklist

- [ ] Run the lab smoke bundle command after package validation:
  ```powershell
  ptm dual-gate-lockin-hall-suite-lab-smoke-bundle data\hall_packages\<package> --overwrite
  ```
- [ ] Confirm read-only identify/probe/preflight checks pass.
- [ ] After hardware runs, use the printed intake command with the returned
  Vxx/+B/-B/0B run folders.
- [ ] Confirm `result_intake.json` and `lab_return/lab_return_manifest.json`
  are present before analysis.

## NPLC Reminder

This return contract does not change measurement settings. It keeps the
returned run folders tied to the package whose Keithley NPLC/range/compliance
and SR860 settings were audited before lab handoff.
