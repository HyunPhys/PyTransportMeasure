# SRS SR860 SCPI Notes

Source manual: `SR860m.pdf` in the project root.

## Minimal Command Subset

The first active SR860 code path is intentionally read-only and conservative.

- `*IDN?`: returns the SR860 identification string.
- `ERRS?`: queries the error status byte.
- `LIAS?`: queries the lock-in status word.
- `OUTP? <parameter>`: reads one lock-in parameter.
- `SNAP? <a>,<b>,<c>`: reads two or three lock-in parameters at one instant.

The manual states that `SNAP?` supports at least two and at most three
parameters. For the first driver implementation, PyTransportMeasure reads
`X`, `Y`, and `R` together with `SNAP? X,Y,R`, then reads phase separately with
`OUTP? THeta`.

## Driver Policy

- Do not reset or reconfigure the SR860 in probe mode.
- Do not enable AC hardware acquisition merely because identify/probe works.
- Keep SR860 configuration fields method-specific, not global.
- Save lock-in readout columns explicitly:
  - `lockin_x_v`
  - `lockin_y_v`
  - `lockin_r_v`
  - `lockin_theta_deg`

## Measurement Settings To Record

The SR860 manual lists the following setting commands that directly affect
lock-in measurement interpretation. PyTransportMeasure recipes may record these
as expected settings, but the current hardware runners do not write them to the
SR860 yet.

- `RSRC(?)`: reference source, internal/external/dual/chop.
- `FREQ(?)`: internal reference frequency, 1 mHz to 500 kHz.
- `SLVL(?)`: sine output amplitude, 1 nV to 2 V.
- `IVMD(?)`: voltage or current input mode.
- `ISRC(?)`: voltage input A or A-B.
- `ICPL(?)`: AC/DC input coupling.
- `IGND(?)`: floating or grounded input shield.
- `IRNG(?)`: voltage input range, 1 V to 10 mV.
- `SCAL(?)`: sensitivity index, 0 to 27.
- `OFLT(?)`: time-constant index, 0 to 21.
- `OFSL(?)`: output filter slope, 6/12/18/24 dB/oct.
- `SYNC(?)`: synchronous filter off/on.

These expected settings are saved in recipe snapshots and metadata so a run can
be interpreted later even before active SR860 configuration is enabled.

## Smoke-Test Commands

```powershell
ptm list-resources
ptm identify --instrument srs_sr860 --address "GPIB0::4::INSTR"
ptm probe --instrument srs_sr860 --address "GPIB0::4::INSTR"
ptm doctor --instrument srs_sr860 --address "GPIB0::4::INSTR"
```

Expected probe fields:

- `address`
- `idn`
- `error_status`
- `lia_status`

## Next Measurement Step

The next measurement phase should add an AC hardware preflight for
`ac_lockin_sweep` that checks both the Keithley source and SR860 before any
source output is enabled. The full `ptm ac-lockin` hardware runner should remain
blocked until that two-instrument preflight passes on the lab laptop.
