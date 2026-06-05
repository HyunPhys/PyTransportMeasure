# Phase 58: SR860 Probe And Keithley NPLC

This phase adds two measurement-core improvements:

- SR860 identify/probe support based on `SR860m.pdf`
- Keithley 2450 NPLC support in recipe, plan, runner, metadata snapshots, and
  GUI form paths

## SR860 Scope

The SR860 driver is intentionally narrow:

- `identify()` sends `*IDN?`
- `probe()` sends `*IDN?`, `ERRS?`, and `LIAS?`
- `read_channels()` sends `SNAP? X,Y,R` and `OUTP? THeta`

This does not yet enable AC hardware acquisition. It prepares the communication
smoke test that must pass before enabling `ptm ac-lockin` on real hardware.

## Keithley NPLC Scope

Keithley source/measure configuration now accepts `nplc` through the common
SMU config. If a recipe sets `instrument.nplc`, `source_instrument.nplc`,
`drain_instrument.nplc`, or `gate_instrument.nplc`, the driver sends:

```text
:SENS:CURR:NPLC <value>
```

Representative hardware smoke recipes now include `nplc: 1.0`.

## Lab Checklist

```powershell
ptm list-resources
ptm identify --instrument srs_sr860 --address "GPIB0::4::INSTR"
ptm probe --instrument srs_sr860 --address "GPIB0::4::INSTR"
ptm doctor --instrument srs_sr860 --address "GPIB0::4::INSTR"
ptm plan configs/recipes/drain_iv_1k_resistor.yaml
```

Confirm:

- SR860 identify string contains `SR860`
- SR860 probe shows `error_status: 0`
- SR860 probe shows `lia_status` as a decimal status value
- Drain I-V plan prints `NPLC: 1`
