# Phase 25daj: Keithley Parameter Visibility

## Summary

Keithley 2450 `NPLC` support was already present in the recipe schema, shared
SMU config builder, SCPI driver, readback comparison, metadata, and hardware
parameter audit. This phase makes that measurement condition more visible at the
places where a human checks the run before enabling output.

## Changes

- Drain I-V plans now label NPLC as `power-line cycles`.
- GUI recipe overview labels voltage/current ranges, compliance, source delay,
  and NPLC with units or physical meaning.
- GUI hardware confirmation now shows voltage range, current range, NPLC,
  source delay, sweep, compliance, and safety preset together.
- Existing measurement-parameter audits remain the authoritative hardware gate
  for missing Keithley range/NPLC settings.

## Lab Checklist

- [ ] In the recipe, confirm each active Keithley block has `nplc`.
- [ ] In the GUI overview or `ptm plan`, confirm NPLC is the intended
      noise/speed tradeoff.
- [ ] Before comparing scans, keep NPLC fixed unless the lab intentionally
      changes integration time.
- [ ] After a hardware run, check `metadata.json` for configured NPLC and
      `configured_*_smu_readback.current_nplc`.
