# Phase 41: GUI Workflow Guide

## Goal

Make the GUI less button-heavy by giving the user a single workflow status view.
The GUI already has separate `Measurement`, `Instruments`, and `Analysis`
workspaces; this phase adds a `Workflow` subtab under `Measurement` so the next
safe action is visible while preparing a run.

## Implemented

- Added a `Workflow` tab in the measurement workspace.
- Tracked these major run-preparation steps:
  - `Check YAML`
  - `Refresh Instruments`
  - `Test Selected Address`
  - `Plan`
  - `Dry Run`
  - `Preflight`
  - `Hardware Run`
- Recipe edits reset only recipe-dependent workflow states.
- Instrument refresh and communication-test status stay visible after recipe
  edits because they describe the current laptop/instrument session.
- Dry-run, preflight, and hardware run completion now update the workflow guide.
- The guide explicitly states that Recipe YAML is the execution source, and that
  form edits must be applied with `Form -> YAML` before they affect runs.

## Design Notes

This phase does not change the measurement runner, instrument driver, safety
logic, data files, or hardware command path. It is intentionally a thin GUI layer
on top of the existing recipe and runner APIs.

Keeping the workflow guide state in the GUI makes it replaceable later. Future
schema-driven form builders, 4-probe options, lock-in workflows, and pulse
methods can add or rename workflow steps without changing the hardware runner.

## User Checklist

- [ ] Start the GUI with `ptm-gui`.
- [ ] Open `Measurement > Workflow`.
- [ ] Confirm all steps initially show `[ ]`.
- [ ] Click `Check YAML` and confirm `Check YAML` changes to `[x]` when valid.
- [ ] Open `Instruments`, click `Refresh Instruments`, and confirm
  `Refresh Instruments` changes to `[x]`.
- [ ] Select the expected address, click `Test Selected Address`, and confirm
  `Test Selected Address` changes to `[x]` when communication passes.
- [ ] Return to `Measurement`, click `Plan`, and confirm `Plan` changes to
  `[x]`.
- [ ] Run a dry-run and confirm `Dry Run` changes to `[x]` after completion.
- [ ] Edit the YAML or form and confirm recipe-dependent steps reset while the
  instrument refresh/test state remains visible.
- [ ] On the lab laptop, run `Preflight` before hardware and confirm the workflow
  guide reflects pass/fail.
