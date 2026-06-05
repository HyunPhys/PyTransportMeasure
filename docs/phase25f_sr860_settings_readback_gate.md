# Phase 25f: SR860 Settings Readback Gate

This phase adds a read-only SR860 configuration verification gate for AC and
dual-gate lock-in hardware paths.

## Scope

- Extend the SR860 driver probe path with read-only setting queries:
  - `RSRC?`
  - `FREQ?`
  - `SLVL?`
  - `IVMD?`
  - `ISRC?`
  - `ICPL?`
  - `IGND?`
  - `IRNG?`
  - `SCAL?`
  - `OFLT?`
  - `OFSL?`
  - `SYNC?`
- Compare declared recipe lock-in expectations against actual SR860 readback in:
  - `ptm ac-lockin-preflight`
  - `ptm dual-gate-lockin-preflight`
- Block preflight when an expected SR860 setting is missing or mismatched.
- Keep SR860 configuration writes deferred to a later smoke-tested phase.

## Policy

This phase does not reset, configure, or otherwise write to the SR860. The
operator should adjust front-panel settings manually, or edit the recipe if the
expectation is wrong, then rerun preflight.

## Lab Checklist

```powershell
ptm probe --instrument srs_sr860 --address "GPIB0::4::INSTR"
ptm ac-lockin-preflight configs/recipes/ac_lockin_hardware_smoke.yaml
ptm dual-gate-lockin-preflight configs/recipes/dual_gate_lockin_limited_active.yaml
```

- Confirm `ptm probe` prints `setting_*` fields.
- Confirm the preflight `Lock-in setting check` lists expected vs actual values.
- Confirm `all expected settings match: True`.
- If a mismatch appears, change the SR860 front panel or recipe before running
  hardware output.
