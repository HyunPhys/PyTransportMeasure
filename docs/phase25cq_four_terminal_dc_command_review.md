# Phase 25cq: Four-Terminal DC Active-Run Command Review

This phase adds a non-executing command review for the future Keithley 2450
four-terminal DC remote-sense runner.

## Commands

Review the proposed active-run SCPI sequence without lab evidence:

```powershell
ptm four-terminal-dc-command-review configs\recipes\four_terminal_dc_schema_draft.yaml
```

Review with attached lab/pre-run evidence:

```powershell
ptm four-terminal-dc-command-review configs\recipes\four_terminal_dc_schema_draft.yaml --preflight-json docs\four_terminal_dc_preflight.json --dry-run-metadata data\raw\<run>\metadata.json --json-output docs\four_terminal_dc_command_review.json
```

## Reviewed Sequence

The review lists the intended active-run order:

- identify Keithley and require `*LANG? == SCPI`
- force output off before configuration
- configure terminal plane, current sense function, NPLC, current range, source
  function, voltage range, source delay, voltage readback, and compliance
- enable current remote sense with `:SENS:CURR:RSEN ON`
- read back `:SENS:CURR:RSEN?` and other blocking settings before output
- start from `:SOUR:VOLT 0`
- enable `:OUTP ON` only after all blocking readbacks pass
- acquire sweep points
- always return to zero, turn output off, and disable remote sense with
  `:SENS:CURR:RSEN OFF`

## Safety Status

This is still not an active hardware path. The report always keeps:

- `active_hardware_run_allowed: false`
- `active_runner_ready: false`

The purpose is to make the future active runner auditable before implementation.
NPLC, ranges, compliance, terminal selection, source delay, remote-sense
readback, and cleanup are treated as required measurement conditions.

## Lab Checklist

- [ ] Run `four-terminal-dc-preflight` with `--json-output`.
- [ ] Run `four-terminal-dc --dry-run` and keep the generated `metadata.json`.
- [ ] Run `four-terminal-dc-command-review` with both evidence files attached.
- [ ] Confirm every evidence check is PASS.
- [ ] Confirm `:SENS:CURR:RSEN ON` appears before `:OUTP ON`.
- [ ] Confirm `:SENS:CURR:RSEN OFF` appears in cleanup.
- [ ] Confirm the report still says `Active hardware run allowed: False`.
- [ ] Do not run a four-terminal DC hardware sweep yet.
