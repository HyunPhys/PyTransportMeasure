# Phase 25w: Keithley Source Delay Config

## Goal

Add optional Keithley 2450 voltage-source delay to the shared SMU configuration
path:

```yaml
instrument:
  id: keithley_2450
  address: GPIB0::2::INSTR
  nplc: 1.0
  source_delay_s: 0.05
```

## Behavior

When `source_delay_s` is present, the Keithley driver sends:

```text
:SOUR:VOLT:DEL <seconds>
```

The value is saved in the normalized `configured_*_smu` metadata snapshot and,
for readback-capable instruments, checked through:

```text
:SOUR:VOLT:DEL?
```

If the readback contradicts the recipe value, the existing SMU readback gate
blocks output before a hardware sweep starts.

## Difference From Runner Delay

`source_delay_s` is an instrument source setting. It is not the same as:

- `sweep.delay_s`
- `gate_sweep.settle_s`
- lock-in `read_settle_s`

Those runner delays still control how long the Python measurement loop waits
between setting a voltage and reading current/lock-in channels. If both
instrument source delay and runner delay are set, the effective measurement
latency can include both.

## Scope

This phase adds source-delay support to the common SMU config, so it applies to
Drain I-V, single-gate, dual-gate, AC lock-in, dual-gate lock-in, active-gate
smoke, and future Keithley-based methods that use the shared config helper.

Auto-zero is intentionally not added in this phase because the local 2450 user
manual search did not provide a matching SCPI command example.
