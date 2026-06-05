# Phase 43: GUI Cooperative Stop

## Goal

Add a safe stop path for GUI-triggered Drain I-V runs without killing the worker
thread or bypassing the runner cleanup path.

## Implemented

- Added a `stop_requested` callback to the Drain I-V runner.
- The runner checks for stop requests before each voltage point and during
  delay periods.
- A requested stop uses the existing interrupted-run path:
  - `completed: false`
  - `interrupted: true`
  - partial `points.csv`
  - `metadata.json`
  - output-off cleanup in `finally`
- Added `Stop Run` to the GUI measurement controls.
- `Stop Run` is enabled during GUI dry-runs and guarded hardware runs.
- Dry-run and hardware workers pass the stop request into the shared core
  runner instead of terminating the thread.

## Design Notes

This is cooperative cancellation. It is not an emergency instrument disconnect
or process kill. The button requests a stop, and the runner stops at the next
safe checkpoint. That keeps the Keithley output-off and partial-save logic in
the same path used for errors and keyboard interrupts.

For future pulse, lock-in, gate sweep, and multi-instrument methods, each method
runner should expose the same style of `stop_requested` hook rather than adding
GUI-specific cancellation logic.

## User Checklist

- [ ] Start the GUI with `ptm-gui`.
- [ ] Run a Drain I-V dry-run with enough points to see progress.
- [ ] Confirm `Stop Run` is enabled while the run is active.
- [ ] Click `Stop Run`.
- [ ] Confirm Progress shows `Stop requested`.
- [ ] Confirm the run finishes with `completed: false` and `interrupted: true`
  in metadata.
- [ ] Confirm partial `points.csv` and `metadata.json` are saved.
- [ ] On the lab laptop, only test hardware stop with a safe resistor setup
  first; confirm Keithley output is off after interruption.
