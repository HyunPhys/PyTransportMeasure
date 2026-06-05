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

These expected settings are saved in recipe snapshots and metadata. AC and
dual-gate lock-in preflight now query these SR860 settings read-only and compare
them against declared recipe expectations before hardware output is enabled.
`ptm sr860-command-review` converts the same recipe fields into hardware-free
SCPI write/readback pairs. This is a review artifact only: measurement runners
still do not write SR860 configuration commands.
`ptm sr860-configure` can apply those settings as a separate guarded SR860-only
operation. It requires `--allow-write`, a hardware approval note, and a
confirmation prompt, and it saves a write/readback transcript.
`ptm sr860-configure-check` verifies the saved transcript against the current
recipe without touching hardware, so stale configure evidence is caught before
preflight or active SMU output.

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
- `setting_reference_source`
- `setting_reference_frequency_hz`
- `setting_sine_output_amplitude_v`
- `setting_input_mode`
- `setting_voltage_input`
- `setting_input_coupling`
- `setting_input_grounding`
- `setting_voltage_input_range_v`
- `setting_sensitivity_index`
- `setting_time_constant_index`
- `setting_filter_slope_index`
- `setting_synchronous_filter`

## Current Measurement Gate

`ptm ac-lockin-preflight` and `ptm dual-gate-lockin-preflight` now report a
`Lock-in setting check`. If a recipe declares an expected SR860 setting, the
preflight requires the actual SR860 readback to match before hardware output can
be enabled. PyTransportMeasure still does not write SR860 configuration
commands in measurement runners.
