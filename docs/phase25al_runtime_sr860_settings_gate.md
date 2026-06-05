# Phase 25al: Runtime SR860 Settings Gate

This phase moves SR860 setting verification from "preflight only" into the
active dual-gate lock-in runners.

## Why

Preflight proves that the recipe, VISA resources, Keithleys, and SR860 are ready
at the time of the check. A real lab run can still drift between preflight and
output enablement if the SR860 front panel is changed. For broader Hall-bar
graphene scans, the runner itself should save and enforce the SR860 readback
immediately before gate output is enabled.

## Behavior

Active dual-gate lock-in sweep and active-gate smoke now save:

- `lockin_settings_readback_available`
- `lockin_settings_readback_check`
- `lockin_settings_readback_matched`
- `lockin_settings_readback_enforced`

If the lock-in probe contains SR860 `setting_*` readback fields, the runner
compares declared recipe settings against the actual SR860 state. A mismatch
raises `SafetyLimitError` with `triggered_limit: lockin_settings_readback`
before either gate output is turned on.

Dry-runs and fake lock-ins that do not provide SR860 setting readback are not
blocked; their metadata records that readback was unavailable and enforcement
was skipped.

## Checklist

- [ ] Run dual-gate lock-in preflight and confirm setting checks pass.
- [ ] Run active-gate smoke.
- [ ] Inspect `metadata.json`.
- [ ] Confirm `lockin_settings_readback_available: true`.
- [ ] Confirm `lockin_settings_readback_matched: true`.
- [ ] Confirm `lockin_settings_readback_enforced: true`.
- [ ] If the run stops with `lockin_settings_readback`, fix the SR860 front
  panel or recipe before retrying.

