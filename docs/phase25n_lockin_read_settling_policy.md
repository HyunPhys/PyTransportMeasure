# Phase 25n: Lock-In Read Settling Policy

## Goal

Make SR860 timing an explicit measurement parameter, not just a note in the
recipe. AC lock-in and dual-gate lock-in runners now wait a configured lock-in
settle interval after the DC/gate settle and before reading X/Y/R/theta.

## Recipe Fields

The shared `lockin` block accepts:

- `time_constant_index`: SR860 time constant index, 0 through 21.
- `settle_time_constants`: multiplier applied to the selected SR860 time
  constant.
- `read_settle_s`: explicit seconds override. If this is set, it wins over the
  multiplier.

Example:

```yaml
lockin:
  time_constant_index: 10
  settle_time_constants: 3.0
```

For the SR860, index 10 is 0.1 s, so this waits 0.3 s before each lock-in read.

## Behavior

- `ptm ac-lockin-plan` and `ptm dual-gate-lockin-plan` print the computed
  `Lock-in read settle`.
- AC lock-in sweeps sleep for the computed settle before each SR860 read.
- Dual-gate lock-in sweeps include the computed settle in the scan readiness
  minimum programmed settle time and sleep before each SR860 read.
- Metadata saves `lockin_time_constant_s`, `lockin_settle_time_constants`, and
  `lockin_read_settle_s`.

## Hardware Notes

Hardware smoke recipes use `settle_time_constants: 3.0` with
`time_constant_index: 10`, giving 0.3 s per lock-in read. Dry-run recipes keep
the default 0 s settle so tests and GUI dry-runs remain fast.

Keithley NPLC remains configured through each SMU block and should be reviewed
alongside the lock-in timing before hardware output is enabled.
