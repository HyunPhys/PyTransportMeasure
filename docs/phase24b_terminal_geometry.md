# Phase 24b - Terminal Geometry Abstraction

This phase makes the measurement topology explicit without enabling unfinished
4-terminal hardware behavior.

## What Changed

- Added `measurement_geometry` to Drain I-V, single-gate, AC lock-in, and pulse
  recipes.
- Supported schema values are currently:
  - `method: two_terminal`, `terminal_count: 2`
  - `method: four_terminal`, `terminal_count: 4`
- Active runners validate that only 2-terminal geometry can execute today.
- 4-terminal recipes parse, but safety validation blocks them before output can
  turn on.
- Plan, validation, inspect, report, AC review, templates, GUI form, and recipe
  overview now show measurement geometry.

## Why

`experiment.contact_geometry` is lab metadata about the device and wiring.
`measurement_geometry` is the electrical method the software is expected to
execute. Keeping those separate matters for Hall bar graphene workflows where
the same sample geometry may be used for 2-terminal DC, 4-terminal DC,
2-terminal AC, and future 4-terminal AC measurements.

## Current Hardware Policy

Current active runners are still 2-terminal. A recipe with:

```yaml
measurement_geometry:
  terminal_count: 4
  method: four_terminal
```

is intentionally rejected by safety validation with
`measurement_geometry_terminal_count`.

## Lab Checklist

- [ ] Confirm existing Drain I-V recipes show `measurement_geometry:
      two_terminal`.
- [ ] Run `ptm validate configs/recipes/drain_iv_1k_resistor.yaml`.
- [ ] Run `ptm plan configs/recipes/drain_iv_1k_resistor.yaml` and confirm both
      `Measurement geometry` and `NPLC` are printed.
- [ ] Do not run a 4-terminal recipe on hardware yet; it should fail validation.
