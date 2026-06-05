# Phase 25bz: Hall Package Hardware Command Gating Review

## Summary

Added a hardware-free review command for active hardware command templates stored
in a Hall-suite acquisition package runbook:

```powershell
ptm dual-gate-lockin-hall-suite-hardware-command-review data\hall_packages\<package> --json-output data\hall_packages\<package>\hardware_command_review.json
```

## What It Checks

The review extracts active `ptm dual-gate-lockin ... --allow-active-sweep`
commands from `acquisition_runbook.md` and verifies each one still has:

- `--allow-active-sweep`
- `--stop-after-new-points`
- `--max-hardware-points`
- `--hardware-approval-note`
- `--accepted-previous-run`

It also checks that `--stop-after-new-points` matches the package `chunk_size`
and `--max-hardware-points` matches the package `max_hardware_points`.

## Why This Matters

Hall-suite packages are designed for lab-laptop execution after review. The
runbook must never silently lose the active hardware safeguards that keep scans
bounded and auditable.

## Lab Checklist

- [ ] Run the hardware command review after package validation.
- [ ] Confirm it prints `Hardware commands guarded: True`.
- [ ] Save `hardware_command_review.json` next to the package.
- [ ] If it fails, regenerate or fix the package before running any active
  hardware command.
