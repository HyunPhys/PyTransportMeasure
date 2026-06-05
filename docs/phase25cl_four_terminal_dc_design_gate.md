# Phase 25cl: Four-Terminal DC Design Gate

This phase adds a non-executing design gate for future Keithley 2450
four-terminal DC measurements.

Command:

```powershell
ptm four-terminal-dc-design-gate
ptm four-terminal-dc-design-gate configs\recipes\<candidate_four_terminal_dc>.yaml --json-output docs\four_terminal_dc_design_gate.json
```

The command does not connect to hardware and does not enable Keithley output.
It records the design requirements that must be satisfied before implementing a
remote-sense / 4-wire DC runner.

## Current Boundary

- Active four-terminal DC hardware runs remain blocked.
- No active code path sends `:SENS:CURR:RSEN ON`.
- No active recipe accepts `dc_sense_mode` yet.
- The design gate always reports `Active hardware run allowed: False`.

## Required Keithley 2450 SCPI Path

For Drain I-V style voltage-source/current-measure remote sense, the design gate
records these future command requirements:

- `*LANG?` must return `SCPI`.
- `:SENS:FUNC "CURR"` selects current measurement.
- `:SENS:CURR:RSEN ON` enables remote sense for current measurement.
- `:SENS:CURR:RSEN?` must be read back before output is enabled.
- `:SOUR:VOLT:ILIM` or accepted `:SOUR:VOLT:ILIMIT` fallback sets current
  compliance.
- `:SOUR:VOLT 0` must run before `:OUTP OFF`.

Resistance-mode four-wire measurement remains a separate future method because
the manual evidence points to `:SENS:RES:RSEN ON`, not the Drain I-V current
measurement command.

## Lab Checklist

- [ ] Run `ptm four-terminal-dc-design-gate`.
- [ ] Confirm it prints `Active hardware run allowed: False`.
- [ ] Confirm the report lists `:SENS:CURR:RSEN ON` and
  `:SENS:CURR:RSEN?`.
- [ ] For a candidate YAML, confirm it declares `measurement_geometry.method:
  four_terminal` and explicit Keithley range/NPLC/compliance values.
- [ ] Do not connect a fragile device for 4-wire DC until schema, driver tests,
  preflight readback, fake metadata, and a resistor smoke recipe exist.
