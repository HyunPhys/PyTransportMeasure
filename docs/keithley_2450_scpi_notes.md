# Keithley 2450 SCPI Notes

Source: `2450-900-01E_Aug_2019_User.pdf` in this repository.

This note summarizes the parts of the Keithley 2450 User Manual that matter for
PyTransportMeasure v0: source voltage, measure current, set current limit, and
run a Drain I-V measurement.

## 1. Command Set Must Be Checked First

The 2450 supports three remote command sets:

- `SCPI`
- `TSP`
- `SCPI2400`

The manual says these command sets cannot be mixed. The instrument is shipped
with `SCPI` selected, but an existing lab instrument may have been changed.

Useful commands:

```text
*LANG?
*LANG SCPI
*LANG TSP
*LANG SCPI2400
```

Changing command set requires a reboot. PyTransportMeasure should query `*LANG?`
before configuring the instrument and should refuse to run v0 Drain I-V unless
the response is `SCPI`.

Manual locations:

- Page 37 / section 3-15: command set overview
- Page 38 / section 3-16: `*LANG?` and `*LANG SCPI`
- Page 103-104 / section 10-3 to 10-4: troubleshooting command set changes

## 2. Basic Output Control

The manual uses these SCPI commands for output state:

```text
:OUTPut:STATe ON
:OUTPut:STATe OFF
```

Examples in later sections also use the short form:

```text
OUTP ON
OUTP OFF
```

For our driver, using `:OUTP ON` and `:OUTP OFF` is acceptable. The runner should
always attempt `:OUTP OFF` on normal completion, safety stop, or unexpected error.

Manual location:

- Page 16 / section 2-5: output on/off commands

## 3. Source Voltage, Measure Current

The repeated pattern in the manual for voltage-source/current-measure operation is:

```text
*RST
SENS:FUNC "CURR"
SENS:CURR:NPLC <nplc>
SENS:CURR:RANG:AUTO ON
SOUR:FUNC VOLT
SOUR:VOLT:RANG <range>
SOUR:VOLT:DEL <seconds>
SOUR:VOLT:ILIM <current_limit>
SOUR:VOLT <voltage>
OUTP ON
READ?
OUTP OFF
```

The order varies across examples, but the important pieces are:

- Set source function to voltage: `SOUR:FUNC VOLT`
- Set measure function to current: `SENS:FUNC "CURR"`
- Optionally set current integration time: `SENS:CURR:NPLC <value>`
- Enable current autorange: `SENS:CURR:RANG:AUTO ON`
- Set current limit on the voltage source: `SOUR:VOLT:ILIM <A>`
- Optionally set a voltage range: `SOUR:VOLT:RANG <V>`
- Optionally set voltage-source delay: `SOUR:VOLT:DEL <seconds>`
- Turn output on only after configuration is complete
- Query readback after configuration and before output when auditing hardware
  runs:
  `SOUR:FUNC?`, `SENS:FUNC?`, `ROUT:TERM?`, `SENS:CURR:NPLC?`,
  `SENS:CURR:RANG?`, `SENS:CURR:RANG:AUTO?`, `SOUR:VOLT:RANG?`,
  `SOUR:VOLT:DEL?`, `SOUR:VOLT:READ:BACK?`, and the accepted current-limit
  query.

Manual examples:

- Page 56 / section 6-7: leakage current measurement
- Page 61 / section 6-12: insulation resistance measurement
- Page 72 / section 7-9: FET linear drain sweep
- Page 86 / section 8-8: battery measurement loop
- Page 97 / section 9-7: solar-cell I-V sweep

## 4. Current Limit Command

For the 2450 SCPI command set, the manual examples use current limit as a
property of the voltage source:

```text
:SOUR:VOLT:ILIMIT 0.01
:SOUR:VOLT:ILIM 0.01
SOUR:VOLT:ILIM 1
SOUR:VOLT:ILIM 460e-3
```

Important observation:

- The User Manual examples do **not** use `SENS:CURR:PROT` for 2450 SCPI.
- `SENS:CURR:PROT` is common on older Keithley/SCPI-style instruments, but it is
  not the command shown in this 2450 User Manual for voltage-source current
  limiting.

For PyTransportMeasure v0, prefer:

```text
:SOUR:VOLT:ILIM <current_limit_a>
```

If that returns undefined header, try the full spelling:

```text
:SOUR:VOLT:ILIMIT <current_limit_a>
```

Before trying fallback commands, query `*LANG?`; if the instrument is not in
`SCPI`, command fallback is likely the wrong fix.

Manual locations:

- Page 56: `:SOUR:VOLT:ILIMIT 0.01`
- Page 61: `:SOUR:VOLT:ILIM 0.01`
- Page 72: `:SOUR:VOLT:ILIM 1`
- Page 86: `SOUR:VOLT:ILIM 460e-3`
- Page 97: `SOUR:VOLT:ILIM 1`

## 5. Terminal Selection

Several manual examples explicitly select rear terminals:

```text
:ROUT:TERM REAR
```

For v0, terminal selection should become a YAML option because lab wiring may
use either front or rear terminals. If unspecified, do not silently assume the
right physical terminal; either use a conservative default and document it or
query/log the active setting.

Manual examples:

- Page 56: leakage current uses rear terminals
- Page 61: insulation resistance uses rear terminals
- Page 72: FET examples use rear terminals

## 6. Manual Loop vs Built-In Sweep

The manual shows two relevant styles.

### Manual/Python Loop Style

Battery example:

```text
SOUR:FUNC VOLT
SOUR:VOLT 1
SOUR:VOLT:READ:BACK ON
SOUR:VOLT:RANG 2
SOUR:VOLT:ILIM 460e-3
SENS:FUNC "CURR"
SENS:CURR:RANG 1
OUTP ON
READ?
TRAC:DATA? <index>, <index>, "defbuffer1", SOUR
OUTP OFF
```

This style is closest to our v0 runner: Python controls each voltage point, then
reads current.

### Built-In Sweep Style

Solar-cell and FET examples:

```text
SENS:FUNC "CURR"
SENS:CURR:NPLC 1
SENS:CURR:RANG:AUTO ON
SOUR:FUNC VOLT
SOUR:VOLT:RANG 2
SOUR:VOLT:ILIM 1
SOUR:SWE:VOLT:LIN 0, 0.55, 56, 0.1
:INIT
*WAI
TRAC:DATA? 1, 56, "defbuffer1", SOUR, READ
```

This is a good future optimization, but v0 should stay with the manual/Python
loop because it is easier to debug point-by-point with real hardware.

Manual locations:

- Page 86: manual repeated `READ?`
- Page 72: FET built-in linear sweep
- Page 97: solar-cell built-in linear sweep

## 7. Recommended v0 Drain I-V SCPI Sequence

Assuming the instrument responds to `*LANG?` with `SCPI`, use this sequence for
the 1 kOhm resistor smoke test:

```text
*RST
*CLS
*LANG?
SENS:FUNC "CURR"
SENS:CURR:RANG:AUTO ON
SOUR:FUNC VOLT
SOUR:VOLT:RANG 0.2
SOUR:VOLT:READ:BACK ON
SOUR:VOLT:ILIM 2e-4
SOUR:VOLT 0
OUTP ON

# For each voltage point:
SOUR:VOLT <point_voltage>
READ?

SOUR:VOLT 0
OUTP OFF
```

If `SOUR:VOLT:ILIM` fails but `*LANG?` is `SCPI`, try:

```text
SOUR:VOLT:ILIMIT 2e-4
```

If both fail, stop and inspect the exact `*IDN?`, `*LANG?`, and `SYST:ERR?`
responses before adding more fallback behavior.

## 8. Implementation Implications

Before changing more driver code, PyTransportMeasure should add a small hardware
probe command that prints:

```text
*IDN?
*LANG?
:SYST:ERR?
```

Then update the Keithley driver to:

- Require `*LANG? == SCPI` for v0.
- Use `SOUR:VOLT:ILIM` first.
- Use `SOUR:VOLT:ILIMIT` as the only documented fallback from this User Manual.
- Stop using `SENS:CURR:PROT` for the 2450 SCPI path.
- Set voltage back to `0 V` before `OUTP OFF` during shutdown.
- Add YAML-controlled terminal selection later: `FRONT` or `REAR`.

## 9. Remote Sense / 4-Wire Notes

The manual shows remote sense commands in different measurement contexts:

```text
SENS:RES:RSEN ON
SENS:CURR:RSEN ON
```

Manual examples:

- Page 48: low-resistance measurement uses `SENS:FUNC "RES"` and
  `SENS:RES:RSEN ON`.
- Page 86: battery measurement includes `SENS:RES:RSEN ON` before a
  voltage-source/current-measure loop.
- Page 97: solar-cell I-V uses `SENS:FUNC "CURR"` and `SENS:CURR:RSEN ON`.

For PyTransportMeasure, do not add remote sense as a global instrument flag.
Treat it as a method-specific capability because the correct SCPI command depends
on whether the method is measuring current or resistance. See
`docs/phase20_4probe_remote_sense_design.md`.
