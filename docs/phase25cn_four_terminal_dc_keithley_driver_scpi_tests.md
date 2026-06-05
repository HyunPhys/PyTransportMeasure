# Phase 25cn: Four-Terminal DC Keithley Driver SCPI Tests

This phase adds a driver-level Keithley 2450 current remote-sense primitive and
fake-VISA tests for its exact SCPI behavior.

Added driver methods:

```python
Keithley2450.configure_current_remote_sense(True)
Keithley2450.configure_current_remote_sense(False)
Keithley2450.read_current_remote_sense()
```

Expected SCPI:

```text
:SENS:CURR:RSEN ON
:SENS:CURR:RSEN OFF
:SENS:CURR:RSEN?
```

## Boundary

- `configure_voltage_source()` does not call remote-sense commands.
- `ptm run` does not call remote-sense commands.
- Four-terminal DC hardware output remains blocked.
- The next phase must add preflight/readback gating before any runner can use
  the driver primitive.

## Checklist

- [ ] Run `python -m pytest tests\test_keithley_2450.py -q`.
- [ ] Confirm voltage-source configuration still does not send
  `:SENS:CURR:RSEN`.
- [ ] Confirm the fake VISA test sees `:SENS:CURR:RSEN ON` and
  `:SENS:CURR:RSEN OFF` only when the dedicated primitive is called.
- [ ] Do not run four-terminal DC hardware yet.
