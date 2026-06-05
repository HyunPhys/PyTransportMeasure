# Phase 25an: AC Lock-In Runtime SR860 Gate

This phase applies the runtime SR860 setting gate to the AC/lock-in sweep
runner.

## What Changed

`ptm ac-lockin` now repeats the SR860 setting check after connecting to the
lock-in and before enabling the Keithley source output. Metadata records:

- `lockin_settings_readback_available`
- `lockin_settings_readback_check`
- `lockin_settings_readback_matched`
- `lockin_settings_readback_enforced`

If the SR860 probe returns `setting_*` readback fields and any declared recipe
setting does not match, the runner stops with
`triggered_limit: lockin_settings_readback` before source output turns on.

Dry-runs with fake lock-ins that do not provide SR860 setting readback remain
allowed; metadata records that readback was unavailable.

## Why

Two-terminal and four-terminal AC measurements should have the same
front-panel drift protection as the dual-gate lock-in path. A preflight pass is
not enough if the SR860 state changes before output is enabled.

## Checklist

- [ ] Run `ptm ac-lockin-preflight`.
- [ ] Confirm every declared SR860 setting matches.
- [ ] Run `ptm ac-lockin`.
- [ ] Inspect `metadata.json`.
- [ ] Confirm `lockin_settings_readback_matched: true`.
- [ ] If the run stops with `lockin_settings_readback`, fix the SR860
  front-panel setting or recipe expectation before retrying.

