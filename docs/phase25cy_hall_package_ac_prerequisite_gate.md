# Phase 25cy: Hall Package Four-Terminal AC Prerequisite Gate

## Purpose

Before moving from single four-terminal AC smoke tests toward Hall-bar
dual-gate packages, the Hall handoff package can now carry explicit evidence
that a four-terminal AC lock-in smoke run passed intake.

## What Changed

`ptm dual-gate-lockin-hall-suite-package` and the approved next-scan package
path now accept:

```powershell
--four-terminal-ac-smoke-intake-json docs\four_terminal_ac_lab_smoke_intake.json
```

The JSON must be a PASS output from:

```powershell
ptm ac-lockin-lab-smoke-intake data\raw\<run> --json-output docs\four_terminal_ac_lab_smoke_intake.json
```

The package command rejects the prerequisite unless it contains:

- `accepted: true`
- four-terminal hardware guard present and accepted
- non-empty hardware approval note
- `lockin_voltage_input: a-b`
- separated excitation contacts and SR860 voltage contacts
- saved Keithley source NPLC, voltage range, current range, and compliance
- point guard count within the saved guard limit

When accepted, the package copies the JSON into `prerequisites/`, records a
summary in `package_manifest.json`, and prints a Measurement Prerequisites
section in `acquisition_runbook.md`.

## Lab Checklist

- [ ] Run the four-terminal AC hardware smoke with the guarded command.
- [ ] Run `ptm ac-lockin-lab-smoke-intake ... --json-output`.
- [ ] Confirm the intake JSON has `accepted: true`.
- [ ] Generate the Hall-suite package with
  `--four-terminal-ac-smoke-intake-json`.
- [ ] Confirm `acquisition_runbook.md` prints `Four-terminal AC smoke intake:
  PASS`.
- [ ] Confirm `package_manifest.json` has
  `prerequisites.four_terminal_ac_smoke_intake`.
- [ ] Run `ptm dual-gate-lockin-hall-suite-validate-package` and confirm PASS.

## NPLC Reminder

The prerequisite gate checks the four-terminal AC Keithley source NPLC. The Hall
suite package separately audits gate1/gate2 Keithley NPLC. Treat both as
measurement conditions when comparing graphene Hall-bar scans.
