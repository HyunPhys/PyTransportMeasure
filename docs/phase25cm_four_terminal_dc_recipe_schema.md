# Phase 25cm: Four-Terminal DC Recipe Schema Draft

This phase adds a non-executing schema draft for future Keithley 2450
remote-sense / four-terminal Drain I-V measurements.

Commands:

```powershell
ptm four-terminal-dc-validate configs\recipes\four_terminal_dc_schema_draft.yaml
ptm four-terminal-dc-design-gate configs\recipes\four_terminal_dc_schema_draft.yaml
```

The schema is intentionally separate from the active `DrainIVRecipe` runner.
It validates the method intent and contact topology, but it does not create an
active hardware execution path.

## Added Recipe Shape

```yaml
measurement_geometry:
  terminal_count: 4
  method: four_terminal
dc_sense_mode: remote_4wire
contacts:
  source_contact: S
  drain_contact: D
  sense_hi_contact: V+
  sense_lo_contact: V-
  terminal_plane: FRONT
implementation_status: schema_draft_non_executable
```

Validation requires:

- `measurement_geometry.method: four_terminal`
- `measurement_geometry.terminal_count: 4`
- `dc_sense_mode: remote_4wire`
- explicit Keithley `voltage_range_v`, `current_range_a`, and `nplc`
- distinct source, drain, sense-hi, and sense-lo contacts
- `instrument.terminal` matching `contacts.terminal_plane` when set
- voltage range covering the sweep

## Current Boundary

- `ptm run` still accepts only active Drain I-V recipes and keeps four-terminal
  DC blocked through the existing safety guard.
- No runner sends `:SENS:CURR:RSEN ON`.
- No preflight reads `:SENS:CURR:RSEN?` yet.

## Lab Checklist

- [ ] Run `ptm four-terminal-dc-validate
  configs\recipes\four_terminal_dc_schema_draft.yaml`.
- [ ] Confirm the output says `Active hardware run allowed: False`.
- [ ] Edit a copy of the schema draft with real contact labels before future
  smoke tests.
- [ ] Do not run a 4-wire DC hardware measurement until driver SCPI tests,
  preflight readback, fake metadata, and resistor smoke recipe phases exist.
