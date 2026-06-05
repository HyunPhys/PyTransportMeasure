# Phase 25p: SMU Configuration Readback

## Goal

Record Keithley source/measure settings immediately after configuration and
before output is enabled. This complements the normalized `configured_*_smu`
intent snapshot with a best-effort instrument/driver readback.

## Readback Keys

The current Keithley 2450 readback hook queries:

- `:SOUR:FUNC?`
- `:SENS:FUNC?`
- `:ROUT:TERM?`
- `:SENS:CURR:NPLC?`
- `:SENS:CURR:RANG?`
- `:SENS:CURR:RANG:AUTO?`
- `:SOUR:VOLT:RANG?`
- `:SOUR:VOLT:READ:BACK?`
- the accepted current-limit query, either `:SOUR:VOLT:ILIM?` or
  `:SOUR:VOLT:ILIMIT?`

Individual query failures are saved as `ERROR ...` strings instead of aborting
the run. Configuration write failures still abort before output is enabled.

## Metadata Keys

The following keys mirror the previous intent snapshots:

- `configured_smu_readback`
- `configured_source_smu_readback`
- `configured_drain_smu_readback`
- `configured_gate_smu_readback`
- `configured_gate1_smu_readback`
- `configured_gate2_smu_readback`

## Hardware Use

After a lab-laptop run, compare `configured_*_smu` with
`configured_*_smu_readback` in `metadata.json`. Pay special attention to NPLC,
current range/autorange, terminal selection, voltage range, and current limit.

Readback happens before output is enabled, so it is safe diagnostic metadata
rather than an extra measurement step.
