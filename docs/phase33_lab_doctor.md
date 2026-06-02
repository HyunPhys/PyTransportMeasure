# Phase 33 - Lab Laptop Doctor

This phase adds a lab-laptop diagnostic command for remote hardware validation.

## Implemented

- Added `ptm doctor`.
- Reports PyTransportMeasure version, Python version, platform, PyVISA version,
  VISA resources, optional address match, and optional Keithley probe results.
- Supports text output and JSON output.
- Supports writing the report to a file.
- Handles PyVISA/resource/probe errors as report fields instead of crashing
  without context.

## Workflow

Basic environment and resource check:

```powershell
ptm doctor
```

Check and probe a Keithley address:

```powershell
ptm doctor --address "GPIB0::2::INSTR"
```

Write a JSON report:

```powershell
ptm doctor --address "GPIB0::2::INSTR" --json --output doctor.json
```

## Intended Use

Run this on the lab laptop before hardware debugging. If a measurement fails
before data is produced, send the doctor report. If a run folder exists, create
a feedback bundle with `ptm feedback-bundle`.
