# Phase 25s: Zero Before Output Off

## Goal

Record and perform an explicit 0 V setpoint before turning Keithley outputs off
in active runners. Keithley 2450 output cleanup already writes `SOUR:VOLT 0`,
but runner-level zeroing gives a method-independent metadata trail and makes
dry-run behavior match hardware intent.

## Metadata

Each `output_state` role now includes:

- `zero_before_off_attempted`
- `zero_before_off_succeeded`
- `zero_before_off_error`
- `zero_before_off_target_v`

The target is currently fixed at `0.0 V`.

## Behavior

During `finally` cleanup, runners:

1. Attempt `set_voltage(0.0)` for each active SMU role.
2. Record success or error in `output_state`.
3. Attempt `output_off`.
4. Close instruments and write metadata.

All active runners use this policy: Drain I-V, single-gate, dual-gate DC,
AC lock-in, dual-gate lock-in, active-gate smoke, and pulse. Pulse cleanup first
returns to the configured base voltage, then applies the common 0 V final
cleanup before output off.

## Hardware Use

After a failed or interrupted scan, check every active role in `metadata.json`.
Do not treat cleanup as fully clean unless both are true:

- `zero_before_off_succeeded: true`
- `off_after_run: true`

If zeroing failed but output off succeeded, repeat only after checking cabling,
instrument state, and the saved error string.
