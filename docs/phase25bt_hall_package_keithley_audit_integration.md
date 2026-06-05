# Phase 25bt: Hall Package Keithley Audit Integration

## Summary

Hall-suite acquisition packages now include Keithley parameter audit artifacts
for every copied Vxx/+B/-B/0B recipe.

Each package writes:

- `keithley_audit/<recipe_key>_keithley_audit.json`
- `keithley_audit/<recipe_key>_keithley_audit.md`

and records the paths plus PASS/MISSING status in `package_manifest.json` under
`keithley_parameter_audits`.

## Why

The Hall-bar workflow depends on comparing multiple scans under matched
measurement conditions. Keithley NPLC, voltage range, current range, source
delay, terminal selection, and compliance should be preserved across Vxx, +B
Vxy, -B Vxy, 0B Vxy, and approved next-scan packages unless the lab deliberately
changes them. Putting the audit inside the package makes that condition visible
at handoff time.

## Workflow Status

`ptm dual-gate-lockin-hall-suite-status <package>` now includes a Keithley
parameter audit stage. A package is lab-review ready only when the required
package files, copied recipes, and Keithley audit artifacts are present and
passing.

## Lab Checklist

- [ ] Open `acquisition_runbook.md` and find the Keithley Parameter Audits
      section.
- [ ] Confirm `package_manifest.json` contains `keithley_parameter_audits`.
- [ ] Confirm every audit record has `ok_for_hardware: true`.
- [ ] Keep the audit JSON files with the lab notebook or feedback bundle.
- [ ] If any audit reports missing NPLC/range values, fix the recipe and
      regenerate the package before preflight.
