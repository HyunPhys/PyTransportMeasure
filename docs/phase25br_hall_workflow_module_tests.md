# Phase 25br: Hall Workflow Module Tests

## Summary

This phase adds direct tests for the reusable `pytransport.hall_workflow`
module. The CLI still has end-to-end coverage, but the workflow logic now also
has API-level checks so future GUI/API layers can call it without relying on
CLI-only tests.

## Covered APIs

- `inspect_dual_gate_lockin_hall_suite_workflow_status`
- `format_dual_gate_lockin_hall_suite_workflow_status`
- `run_dual_gate_lockin_hall_suite_approved_next_scan_rehearsal`

## Why

Hall-suite operation is becoming a real measurement workflow:

1. create compatible longitudinal/Hall recipes
2. package them for lab acquisition
3. run/review/intake acquired data
4. analyze Hall transport
5. approve the next scan
6. rehearse the approved package without hardware
7. hand the package to the lab laptop

Keeping reusable workflow tests outside CLI argument parsing helps prevent the
CLI from becoming the only reliable interface.

## Verification

- status inspection works from a package directory
- missing package manifests fail clearly
- approved next-scan rehearsal runs through fake acquisition, intake, analysis,
  review, and proposal using the module API directly
- rehearsal is blocked when approved-next-scan provenance is absent

## Lab Checklist

- [ ] Before handing a package to the lab laptop, run the workflow status
      command and confirm required package stages pass.
- [ ] For approved next-scan packages, run dry-run rehearsal locally before
      hardware acquisition.
- [ ] Confirm rehearsal artifacts exist under `dry_run_rehearsal`.
- [ ] Confirm the lab package still preserves Keithley NPLC/range/compliance
      and SR860 settings.
