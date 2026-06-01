# Phase 20 - 4-Probe / Remote-Sense Design Spike

This phase does not implement 4-probe measurement. It records the Keithley 2450
manual evidence, the intended architecture, and the smoke-test checklist for a
future implementation.

## Manual Evidence

Source: `2450-900-01E_Aug_2019_User.pdf` in this repository.

Relevant findings from the Keithley 2450 User Manual:

- Page 15 describes the SENSE HI and SENSE LO terminals. Sense leads measure the
  DUT voltage and remove force-lead voltage-drop error from the measurement.
- Pages 43-45 describe four-wire Kelvin connections for low-resistance
  measurements. FORCE HI/LO carry source current; SENSE HI/LO measure voltage at
  the DUT. Front and rear terminals must not be mixed.
- Page 46 describes "four-wire (remote sense) mode" for low-resistance
  measurement.
- Page 48 gives the SCPI low-resistance sequence:
  ```text
  SENS:FUNC "RES"
  SENS:RES:RANG:AUTO ON
  SENS:RES:OCOM ON
  SENS:RES:RSEN ON
  ```
- Page 86 gives a battery example that sets remote sense before voltage-source /
  current-measure operation:
  ```text
  SENS:RES:RSEN ON
  SOUR:FUNC VOLT
  SOUR:VOLT:READ:BACK ON
  SENS:FUNC "CURR"
  ```
- Page 97 gives a solar-cell I-V example for voltage-source / current-measure
  operation:
  ```text
  SENS:FUNC "CURR"
  SENS:CURR:RANG:AUTO ON
  SENS:CURR:RSEN ON
  SOUR:FUNC VOLT
  SOUR:VOLT:RANG 2
  SOUR:VOLT:ILIM 1
  ```

The important conclusion is that remote sense should not be added as a vague
global flag. The SCPI command depends on the measurement function:

- Current-measure Drain I-V style: `SENS:CURR:RSEN ON`
- Resistance-measure style: `SENS:RES:RSEN ON`

## Design Decision

Do not add `sense_mode` to the active v0/v1 recipe schema yet.

Future implementation should add remote sense as a method-specific capability:

- Drain I-V extension:
  - recipe field candidate: `drain_sense_mode: local_2wire | remote_4wire`
  - SCPI for remote mode: `SENS:CURR:RSEN ON`
  - SCPI for local mode should be verified before implementation; expected form
    is `SENS:CURR:RSEN OFF`
  - metadata records the selected sense mode and command used
- Future resistance method:
  - separate recipe family, not a Drain I-V flag
  - SCPI for remote mode: `SENS:FUNC "RES"` plus `SENS:RES:RSEN ON`
  - SCPI for local mode should be verified before implementation; expected form
    is `SENS:RES:RSEN OFF`
  - optional offset compensation policy

The instrument driver can expose a small capability later, for example:

```python
configure_remote_sense(measurement_function: str, enabled: bool) -> None
```

The runner or method handler should decide which `measurement_function` applies.

## Implementation TODO

- Add a small enum only when implementing:
  - `local_2wire`
  - `remote_4wire`
- Add recipe validation that rejects remote sense unless the method supports it.
- Add plan output that clearly prints `Sense mode: remote_4wire`.
- Add metadata fields:
  - `sense_mode`
  - `remote_sense_command`
  - `sense_terminal_warning_acknowledged`
- Add fake-SMU support that records metadata only; fake physics should not claim
  improved lead resistance accuracy unless a dedicated fake model is added.
- Add driver unit tests for exact SCPI sequence:
  - local mode should not silently enable remote sense
  - remote Drain I-V mode should send `SENS:CURR:RSEN ON`
  - output-off behavior must remain unchanged
- Add a hardware smoke recipe only after the driver command test exists.

## Hardware Smoke-Test Checklist

- [ ] Use a known resistor or resistor network, not a fragile device.
- [ ] Confirm Keithley command set is SCPI.
  ```powershell
  ptm probe --instrument keithley_2450 --address "GPIB0::2::INSTR"
  ```
- [ ] Confirm front or rear terminal use; do not mix front and rear terminals.
- [ ] Wire FORCE HI/LO to carry source current.
- [ ] Wire SENSE HI/LO as close to the DUT terminals as possible.
- [ ] Confirm sense leads are connected before enabling remote sense.
- [ ] Run a 2-wire baseline at conservative voltage/current.
- [ ] Run a 4-wire smoke recipe with the same limits.
- [ ] Confirm output turns off after completion, safety stop, and interrupt.
- [ ] Compare 2-wire and 4-wire fitted resistance for a setup where lead
  resistance is non-negligible.

## Current Boundary

No active code path sends `SENS:CURR:RSEN`, `SENS:RES:RSEN`, or any remote-sense
SCPI command after this phase. No active recipe accepts a 4-probe field. This is
intentional until the future implementation TODO is completed.
