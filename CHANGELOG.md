# Changelog

All notable changes to PyTransportMeasure will be documented here.

This project uses semantic-ish versioning:

- Patch versions: bug fixes and documentation updates that do not change user workflows.
- Minor versions: new measurement methods, new CLI commands, GUI features, or artifact schema additions.
- Major versions: breaking recipe, metadata, CLI, or hardware-control behavior changes.

## v0.1.0 - 2026-06-01

Initial public development snapshot.

### Added

- Keithley 2450 Drain I-V hardware core.
- Conservative safety presets and software current-limit checks.
- Dry-run fake SMU path.
- CSV points, JSON metadata, recipe snapshots, and safety snapshots.
- Summary, SVG plot, Markdown report, and quality-check artifacts.
- Forward/backward and multi-segment Drain I-V sweeps.
- Batch, scheme, and campaign workflows.
- Single-gate dry-run foundation.
- SR860 / AC lock-in dry-run foundation.
- Pulse measurement dry-run foundation.
- PySide6 GUI foundation for plan preview and dry-run artifacts.
- Method registry for saved-run summary, plot, report, inspect, campaign, and plan dispatch.

### Notes

- Hardware-verified path is currently Keithley 2450 Drain I-V.
- Single-gate hardware, SR860 hardware acquisition, pulse hardware, and GUI hardware controls remain intentionally gated behind future smoke-test phases.
