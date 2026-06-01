# Phase 21 - SR860 / Lock-In Foundation

This phase adds the first lock-in foundation without connecting SR860 readout to
any active measurement runner.

## What Changed

- Added a common lock-in protocol:
  - `LockInAmplifier`
  - `LockInReading`
- Added standard lock-in point column names:
  - `lockin_x_v`
  - `lockin_y_v`
  - `lockin_r_v`
  - `lockin_theta_deg`
- Added `FakeLockIn` for dry-run development and tests.
- Added `LockInConfig` for future method-specific recipes.
- Added a template SR860 instrument config:
  - `configs/instruments/srs_sr860.yaml`

## Current Boundary

At the time this phase was completed, no active measurement runner read from a
lock-in. A later dry-run-only AC lock-in skeleton may use `FakeLockIn`, but real
SR860 hardware readout remains inactive until a hardware driver and smoke test
are added.

The current Drain I-V and single-gate workflows remain unchanged. This phase
only prepares the capability surface needed for future AC or lock-in-assisted
measurement methods.

## Timing Policy

Future lock-in-enabled methods should choose one explicit timing mode:

- `after_dc_settle`: set source point, wait for DC settle, then read lock-in once
- `continuous`: acquire lock-in samples across a dwell window
- `external_trigger`: rely on instrument or experiment trigger synchronization

The first implementation should start with `after_dc_settle` because it matches
the existing point-by-point runner style and is easiest to validate on hardware.

## Future Implementation Checklist

- [ ] Add an SR860 hardware driver only after confirming the exact SCPI readout
  commands on the real instrument.
- [ ] Add an active method recipe that owns the lock-in block, rather than adding
  lock-in fields to every existing recipe.
- [ ] Add dry-run data generation using `FakeLockIn`.
- [ ] Add point columns for lock-in readout.
- [ ] Add lock-in-aware summary, plot, report, and campaign fields.
- [ ] Add a hardware smoke-test recipe with conservative defaults.
- [ ] Confirm failure handling closes the lock-in session and turns off any
  source instruments.
