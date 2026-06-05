# Phase 25dai: Guarded SR860 Configure

## Summary

This phase adds a guarded SR860-only configuration command:

```powershell
ptm sr860-configure dual_gate_lockin_sweep configs\recipes\dual_gate_lockin_four_terminal_dry_run.yaml --allow-write --hardware-approval-note "<lab approval>" --json-output docs\sr860_configure.json --yes
```

The command applies the SR860 settings declared in an AC/lock-in recipe and
queries each setting immediately after writing it. It does not touch Keithley
SMUs and does not run a measurement sweep.

## Guard Policy

The command is blocked unless all of these are true:

- the recipe passes the SR860 measurement-parameter audit
- the user passes `--allow-write`
- `--hardware-approval-note` is non-empty
- the confirmation prompt is accepted, unless `--yes` is used

This matters because `SLVL` can change the SR860 sine output amplitude. Treat
SR860 configure as a hardware-affecting action even though it does not enable a
Keithley output.

## Saved Evidence

The JSON output records:

- command review
- lab approval note
- probe before setting writes
- write/readback transcript
- probe after setting writes
- completion and error fields

## Lab Checklist

- [ ] Run `ptm sr860-command-review ...` first and inspect every command.
- [ ] Confirm SR860 output wiring and amplitude are safe for the connected
  device or dummy load.
- [ ] Run `ptm sr860-configure ... --allow-write --hardware-approval-note ...`.
- [ ] Confirm the saved JSON reports `completed: true` and every transcript row
  has `matched: true`.
- [ ] Run `ptm sr860-configure-check ... docs\sr860_configure.json` before using
  the transcript as evidence for the current recipe.
- [ ] Run lock-in preflight after configuration before any SMU output.
