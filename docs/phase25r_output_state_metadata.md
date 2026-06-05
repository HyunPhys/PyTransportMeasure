# Phase 25r: Output State Metadata

## Goal

Track Keithley output state transitions consistently across active runners. This
is especially important for multi-SMU Hall-bar workflows where one output can be
enabled before another instrument or safety check fails.

## Metadata

Every active runner now writes an `output_state` block. Each SMU role records:

- `output_on_attempted`
- `enabled`
- `output_on_error`
- `output_off_attempted`
- `off_after_run`
- `output_off_error`

Roles are method-specific:

- Drain I-V: `instrument`
- Single-gate: `drain`, `gate`
- Dual-gate DC: `drain`, `gate1`, `gate2`
- AC lock-in: `source`
- Dual-gate lock-in and active-gate smoke: `gate1`, `gate2`
- Pulse: `source`

## Behavior

The runners update `output_state` around every output-on and output-off call.
Cleanup attempts all relevant outputs even if one off call fails, and records
the error in metadata. Existing dual-gate lock-in compatibility fields
`gate_outputs_enabled` and `outputs_off_after_run` are still maintained.

## Hardware Use

After a partial or failed run, inspect `metadata.json`:

- `output_on_attempted: false` means the run stopped before enabling that role.
- `enabled: false` and `off_after_run: true` means cleanup reported success.
- `output_off_error` means the software attempted cleanup but the instrument
  reported an error or communication failed.

Do not treat a broader scan as safe to repeat until every active role has a
clean off record.
