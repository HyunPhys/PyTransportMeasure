# Phase 25bw: Keithley NPLC Recipe Range Guard

## Summary

Keithley 2450 NPLC is now treated as a bounded measurement condition, not only
as an optional numeric recipe field.

The shared `InstrumentConfig.nplc` recipe field accepts values from `0.01` to
`10`. This catches accidental values before hardware preflight or output setup.

## Why This Matters

NPLC controls the Keithley current integration time in power-line cycles. Larger
values improve current averaging but slow scans. For graphene Hall-bar scans,
changing NPLC changes the measurement condition and should be recorded as a
deliberate lab decision.

## Implementation

- Added central Keithley NPLC constants in `pytransport.instrument_specs`.
- Applied the bounds to the shared recipe schema used by Drain I-V, single-gate,
  AC lock-in, pulse, dual-gate, and Hall-suite recipes.
- Extended Keithley hardware-parameter audit text to print the valid NPLC recipe
  range.
- Added tests that reject out-of-range NPLC values.

## Lab Checklist

- [ ] Confirm every active Keithley recipe block has an explicit `nplc`.
- [ ] Use values in the supported recipe range `0.01` to `10`.
- [ ] Keep NPLC fixed when comparing repeated Hall scans unless the lab
  intentionally changes the noise/speed tradeoff.
- [ ] Check `metadata.json` after hardware runs for `configured_*_smu.nplc` and
  `configured_*_smu_readback.current_nplc`.
