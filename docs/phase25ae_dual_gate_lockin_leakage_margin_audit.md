# Phase 25ae: Dual-Gate Lock-In Leakage Margin Audit

This phase makes gate leakage margin visible in the dual-gate lock-in
acceptance audit.

## Scope

`ptm dual-gate-lockin-audit` now reports:

- gate1 maximum absolute leakage current,
- gate2 maximum absolute leakage current,
- gate1 leakage/compliance margin,
- gate2 leakage/compliance margin.

The values are computed from `points.csv` and the recipe snapshot saved in
`metadata.json`.

## Policy

Compliance hits or leakage above the configured compliance are acceptance
errors. If leakage remains below compliance but the leakage/compliance margin is
less than 10x, the audit records a warning. The run can still pass, but the
warning is a cue to inspect the device before expanding gate range or point
count.

## Lab Checklist

- Run `ptm dual-gate-lockin-audit ... --write-report` after a limited active
  sweep.
- Confirm leakage maxima are plausible for the device and wiring.
- Confirm both leakage/compliance margins are comfortably above 10x before
  using the run as evidence for a broader scan.
- Treat any `gate*_leakage_margin` warning as a manual review item before
  increasing scan size.
