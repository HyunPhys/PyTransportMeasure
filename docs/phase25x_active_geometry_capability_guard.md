# Phase 25x: Active Geometry Capability Guard

## Goal

Make the current active measurement boundary explicit: all active runners
currently support `two_terminal` geometry only. Future `four_terminal` support
must be implemented as a method capability, not accidentally accepted by an
existing two-terminal runner.

## Behavior

Safety validation now checks both:

- `measurement_geometry.method`
- `measurement_geometry.terminal_count`

If a recipe declares:

```yaml
measurement_geometry:
  method: four_terminal
  terminal_count: 4
```

the active runner is blocked before hardware output with:

```text
triggered_limit: measurement_geometry_method
```

If a future or malformed recipe reaches safety validation with
`method: two_terminal` but `terminal_count: 4`, it is blocked with:

```text
triggered_limit: measurement_geometry_terminal_count
```

## Why

This keeps the software honest while preparing for 4-probe work. A
four-terminal Hall-bar or Kelvin measurement should eventually select a method
that explicitly owns the remote-sense or separate-voltage-readout sequence.
Until then, the existing Drain I-V, single-gate, dual-gate, AC lock-in,
dual-gate lock-in, and pulse runners remain two-terminal only.

## Future Direction

When 4-probe support is implemented, the new method should declare:

- supported geometry
- exact Keithley remote-sense SCPI sequence
- sense-lead wiring checklist
- metadata fields for sense mode and remote-sense command
- fake-instrument behavior that records the selected mode without claiming
  unsupported physics
