# Phase 25bu: Hall Package SR860 Audit Integration

## Summary

Hall-suite acquisition packages now include SR860 setting audit artifacts for
every copied Vxx/+B/-B/0B recipe.

Each package writes:

- `lockin_audit/<recipe_key>_sr860_audit.json`
- `lockin_audit/<recipe_key>_sr860_audit.md`

and records the paths plus PASS/REVIEW status in `package_manifest.json` under
`lockin_setting_audits`.

## What Is Recorded

- SR860 address and enabled state
- channel list and read timing
- declared expected SR860 settings
- sensitivity index
- time constant index and derived seconds
- settle multiplier or explicit read settle seconds

## Why

For Hall-bar measurements, the lock-in configuration is a measurement condition
alongside Keithley NPLC/ranges/compliance. The package now carries both sets of
provenance before hardware acquisition, so the lab laptop can compare the
declared settings against SR860 preflight/readback.

## Lab Checklist

- [ ] Confirm package folder contains `lockin_audit/`.
- [ ] Confirm every copied recipe has `*_sr860_audit.json` and `.md`.
- [ ] Confirm `package_manifest.json` contains `lockin_setting_audits`.
- [ ] Confirm each audit has `ok_for_hardware: true`.
- [ ] During preflight, compare SR860 readback against the expected settings in
      the audit artifact.
