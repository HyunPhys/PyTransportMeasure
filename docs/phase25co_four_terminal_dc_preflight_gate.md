# Phase 25co: Four-Terminal DC Preflight Readback Gate

This phase adds the first hardware-facing, non-executing gate for future
Keithley 2450 four-terminal DC measurements.

## Commands

Recipe/preflight structure only:

```powershell
ptm four-terminal-dc-preflight configs\recipes\four_terminal_dc_schema_draft.yaml --dry-check
```

Lab laptop readback check:

```powershell
ptm four-terminal-dc-preflight configs\recipes\four_terminal_dc_schema_draft.yaml
```

Optional JSON artifact:

```powershell
ptm four-terminal-dc-preflight configs\recipes\four_terminal_dc_schema_draft.yaml --json-output docs\four_terminal_dc_preflight.json
```

## What It Checks

- four-terminal geometry and `dc_sense_mode: remote_4wire`
- distinct force/sense contacts
- matching Keithley terminal plane
- explicit Keithley `voltage_range_v`, `current_range_a`, and `nplc`
- explicit sweep current compliance
- Keithley command set is `SCPI`
- `:SENS:CURR:RSEN?` is readable
- best-effort readback availability for terminal, NPLC, current range, and
  voltage range

## Safety Status

`Active hardware run allowed` remains `False`. This command does not implement
a four-terminal DC runner and does not enable output. It is a gate that proves
the recipe and readback path are ready before a later runner phase is allowed.

NPLC is treated as a measurement condition, not a UI detail. A future active
four-terminal runner must preserve explicit NPLC in the recipe, setup command,
readback snapshot, metadata, and lab notebook artifacts.

## Lab Checklist

- [ ] Confirm the Keithley 2450 command set is SCPI.
- [ ] Confirm the four-terminal fixture contacts match `contacts.*` in the
  recipe.
- [ ] Confirm `instrument.nplc`, `voltage_range_v`, `current_range_a`, and
  `sweep.current_compliance_a` are deliberate values.
- [ ] Run the `--dry-check` command first and confirm it passes.
- [ ] Run the hardware preflight command on the lab laptop.
- [ ] Confirm `Remote sense readback (:SENS:CURR:RSEN?)` prints a value, not an
  `ERROR ...` string.
- [ ] Confirm terminal, NPLC, current range, and voltage range readback checks
  are available or record any unavailable field.
- [ ] Confirm `Active hardware run allowed: False`.
- [ ] Do not run a four-terminal DC hardware sweep yet.
