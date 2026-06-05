# Phase 25cv: Four-Terminal AC Contact Topology Guard

This phase makes four-terminal AC lock-in recipes explicit about Hall-bar wiring
before any SR860 differential voltage path is promoted beyond dry-run.

## Recipe Requirement

For `measurement_geometry.method: four_terminal`, AC lock-in recipes now require:

```yaml
lockin:
  input_mode: voltage
  voltage_input: a-b
topology:
  source_contact: S
  drain_contact: D
  lockin_input_mode: voltage
  lockin_input_contacts: [Vxx+, Vxx-]
  excitation_contacts: [S, D]
```

The lock-in voltage contacts must be distinct from each other and must not
overlap the source/drain excitation contacts.

## Why

Hall-bar graphene measurements depend on knowing which pads carry excitation
and which pads are sensed by the SR860. A bare `four_terminal` geometry label is
not enough to reproduce or audit a measurement.

Plans and reports now print the AC lock-in contact topology, so saved run
folders remain understandable without reopening the original recipe file.
