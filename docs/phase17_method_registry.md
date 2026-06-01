# Phase 17 - Method Registry And Saved-Run Dispatch

This phase adds a small method registry for saved-run behavior. The goal is to
make future methods easier to add without spreading `measurement_type` checks
through the CLI, campaign, scheme review, and inspect code.

## What Changed

- Added `pytransport/method_registry.py`.
- Registered the current saved-run methods:
  - `drain_iv`
  - `single_gate_sweep`
- Centralized these method-specific behaviors:
  - summary function
  - summary formatter
  - plot writer
  - report writer
  - campaign summary fields
  - expected artifact filenames
  - scheme step type mapping
- Updated generic saved-run commands to dispatch through the registry:
  - `ptm summarize <run_dir>`
  - `ptm plot <run_dir>`
  - `ptm report <run_dir>`
- Updated `inspect-run`, campaign collection, and scheme review summary dispatch
  to use the registry.

## Why This Matters

Before this phase, support for Drain I-V and single-gate saved runs was handled
with local `if measurement_type == ...` branches in several modules. That works
for two methods, but it does not scale cleanly to 4-probe, AC, lock-in, pulse,
or GUI-driven workflows.

The registry gives each measurement method one obvious place to declare how its
saved data should be summarized, plotted, reported, and included in campaigns.

## Current Boundary

This phase does not implement a new measurement method. It prepares the saved-run
dispatch layer so future methods can be added with less CLI and review churn.

Runner dispatch is still partly command-specific:

- `ptm run` remains the Drain I-V runner.
- `ptm single-gate` remains the single-gate runner.
- scheme execution still has method-specific execution functions.

That is acceptable for now because the riskier hardware-running path should be
moved more carefully than the saved-run review path.

## Follow-Up

- Extend the registry from saved-run review dispatch into planning and runner
  dispatch.
- Add method descriptors for future 4-probe, lock-in, AC, and pulse methods only
  after their recipe schema and dry-run behavior are defined.
- Keep GUI review pages backed by the same registry rather than duplicating
  measurement-type conditionals.

