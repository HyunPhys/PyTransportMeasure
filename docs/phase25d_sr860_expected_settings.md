# Phase 25d: SR860 Expected Settings Snapshot

This phase makes lock-in measurement parameters explicit without enabling active
SR860 reconfiguration.

## Why

AC and lock-in measurements are not fully described by the saved X/Y/R/theta
values alone. The SR860 reference, input, sensitivity, and filter settings affect
how the saved data should be interpreted. These settings should be visible in
the recipe and metadata before hardware runs are expanded.

## Added Recipe Fields

The shared `lockin` block now accepts:

- `reference_source`
- `reference_frequency_hz`
- `sine_output_amplitude_v`
- `input_mode`
- `voltage_input`
- `input_coupling`
- `input_grounding`
- `voltage_input_range_v`
- `sensitivity_index`
- `time_constant_index`
- `filter_slope_db_per_oct`
- `synchronous_filter`

The field ranges follow the SR860 manual command set summarized in
`docs/sr860_scpi_notes.md`.

## Policy

These fields are expected settings. They are validated, printed in plans, and
saved in recipe snapshots and metadata. Current hardware runners still do not
write these settings to the SR860. The operator must confirm the SR860 front
panel before hardware runs until an explicit SR860 configuration phase is
implemented and smoke-tested.

## Next Step

Add dual-gate lock-in hardware preflight that checks two Keithley resources and
one SR860 resource before any gate output can be enabled.
