# Phase 25dae: Hall Lab Smoke Audit Collector

## Summary

This phase adds one command that runs the package-local measurement-parameter
audits for every Hall-suite recipe:

```powershell
ptm dual-gate-lockin-hall-suite-lab-smoke-audits data\hall_packages\<package> --overwrite
```

It is still hardware-free. It validates the package, loads the copied recipes,
and writes audit artifacts under `lab_smoke/`.

## Outputs

- `lab_smoke/measurement_parameter_audits.json`
- `lab_smoke/measurement_parameter_audits.md`
- `lab_smoke/<recipe_key>_measurement_parameter_audit.json`
- `lab_smoke/<recipe_key>_measurement_parameter_audit.md`

Each per-recipe audit includes the combined Keithley/SR860 hardware-readiness
check used by `ptm measurement-parameter-audit`.

## Lab Checklist

- [ ] Generate or refresh the lab smoke bundle.
- [ ] Run `ptm dual-gate-lockin-hall-suite-lab-smoke-audits ... --overwrite`.
- [ ] Confirm the summary reports `Hardware-ready: True`.
- [ ] Confirm every recipe row reports PASS for both SMU and SR860.
- [ ] Continue to hardware preflight only after the audit collector passes.
