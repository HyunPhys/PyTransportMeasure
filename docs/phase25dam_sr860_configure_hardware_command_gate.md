# Phase 25dam: SR860 Configure Evidence On Hardware Commands

## Summary

This phase carries the optional SR860 configure evidence gate from preflight into
guarded lock-in hardware command entry points.

Commands that now accept `--sr860-configure-json`:

- `ptm ac-lockin`
- `ptm dual-gate-lockin-smoke`
- `ptm dual-gate-lockin-active-smoke`
- `ptm dual-gate-lockin`

The option is ignored by dry-runs because no hardware preflight is required.

## Why This Matters

The active commands rerun preflight internally immediately before hardware
readout or output. If the operator required SR860 configure evidence during a
manual preflight, the same evidence file should be required again at the command
that can touch hardware. Otherwise the final command could accidentally run with
a stale SR860 setup transcript.

## Lab Checklist

- [ ] Run `ptm sr860-configure ... --json-output docs\sr860_configure.json`.
- [ ] Run lock-in preflight with `--sr860-configure-json`.
- [ ] Run the guarded hardware command with the same `--sr860-configure-json`.
- [ ] If the internal preflight prints `SR860 configure evidence check` with
      `OK: False`, stop and regenerate the SR860 configure evidence.
