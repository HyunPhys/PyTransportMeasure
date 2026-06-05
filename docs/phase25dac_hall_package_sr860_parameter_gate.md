# Phase 25dac: Hall Package SR860 Parameter Gate

## Summary

This phase connects the SR860 measurement-parameter audit to Hall acquisition
packages. Hall packages no longer treat SR860 audit readiness as only
`sensitivity_index` and `time_constant_index`. The package audit now applies
the same SR860 hardware-ready policy used by:

```powershell
ptm measurement-parameter-audit dual_gate_lockin_sweep <recipe>
```

## What Changed

- Hall package SR860 audit JSON now includes `hardware_parameter_audit`.
- `measurement_condition_audits.records` now labels SR860 records as
  `lockin_hardware_parameters`.
- SR860 package records include:
  - `missing_required_parameters`
  - `settle_policy_ok`
  - stricter `ok_for_hardware`
- Package validation fails when SR860 hardware parameters are incomplete.
- Acquisition runbooks now call the section `SR860 Measurement Parameter
  Audits`.

## Why

For Hall-bar dual-gate lock-in scans, SR860 settings are part of the
measurement condition. A package should not be lab-handoff ready if the recipe
omits excitation amplitude, input range, input wiring, sensitivity, time
constant, filter slope, synchronous filter state, or a positive settle policy.

## Lab Checklist

- [ ] Regenerate the Hall acquisition package.
- [ ] Open `package_manifest.json`.
- [ ] Confirm `measurement_condition_audits.ok_for_hardware` is `true`.
- [ ] Confirm each SR860 record has `audit_type: lockin_hardware_parameters`.
- [ ] Confirm each SR860 record summary has no
      `missing_required_parameters`.
- [ ] Confirm `settle_policy_ok: true`.
- [ ] Run package validation before handoff:
  ```powershell
  ptm dual-gate-lockin-hall-suite-validate-package data\hall_packages\<package>
  ```
