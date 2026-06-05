# Phase 25ca: Hall Package Handoff Summary Index

## Summary

Added a package-local handoff summary command:

```powershell
ptm dual-gate-lockin-hall-suite-handoff-summary data\hall_packages\<package> --overwrite
```

The command creates:

- `handoff_summary/handoff_summary.md`
- `handoff_summary/handoff_summary.json`
- `handoff_summary/package_validation.json`
- `handoff_summary/lab_smoke_bundle.json`
- `handoff_summary/hardware_command_review.json`

## Purpose

Package validation, lab smoke checklist generation, and hardware command review
remain separate detailed artifacts. This summary gives the lab notebook one
compact PASS/REVIEW page while preserving the detailed JSON audit trail.

## Lab Checklist

- [ ] Run package validation.
- [ ] Generate the lab smoke bundle.
- [ ] Review hardware command guards.
- [ ] Run the handoff summary command.
- [ ] Attach `handoff_summary.md` to the lab notebook entry.
- [ ] Proceed to lab-laptop preflight only if it says `Ready for lab handoff:
  True`.
