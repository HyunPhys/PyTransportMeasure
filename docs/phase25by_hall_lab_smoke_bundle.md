# Phase 25by: Hall-Suite Lab Handoff Smoke Bundle

## Summary

Added a package-local smoke checklist generator:

```powershell
ptm dual-gate-lockin-hall-suite-lab-smoke-bundle data\hall_packages\<package> --overwrite
```

The command is hardware-free. It validates the package first, then writes:

- `lab_smoke/lab_smoke_checklist.md`
- `lab_smoke/lab_smoke_bundle.json`
- `lab_smoke/package_validation.json`

## Purpose

The acquisition package already contains a detailed runbook. This phase adds a
shorter lab-laptop checklist for the first communication and preflight steps
before any active hardware output command.

## Checklist Contents

- `ptm dual-gate-lockin-hall-suite-validate-package`
- `ptm list-resources`
- read-only `ptm identify` commands for the two Keithleys and SR860
- read-only `ptm probe` commands for the two Keithleys and SR860
- suite check and suite plan commands
- one `ptm dual-gate-lockin-preflight` command per packaged recipe

## Lab Checklist

- [ ] Generate the smoke bundle after package validation passes.
- [ ] Move the package folder and ZIP to the lab laptop.
- [ ] Run the checklist top to bottom before any active hardware command.
- [ ] Confirm both Keithleys identify as model 2450.
- [ ] Confirm the SR860 identify response contains SR860.
- [ ] Confirm every preflight reports OK.
