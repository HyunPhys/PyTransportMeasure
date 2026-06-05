# Phase 25q: SMU Readback Match Gate

## Goal

Prevent hardware output from enabling when a Keithley configuration readback
contradicts the intended SMU settings. This converts the previous readback
metadata into a pre-output safety gate.

## Checked Values

For instruments that provide SMU readback, the runner checks:

- source function contains `VOLT`
- sense function contains `CURR`
- voltage readback is on
- source current limit matches `current_compliance_a`
- terminal matches the requested `FRONT` or `REAR`, allowing Keithley-style
  abbreviations such as `FRON`
- NPLC matches when recipe NPLC is explicit
- voltage range matches when explicit
- current range matches when explicit
- current autorange is on when no explicit current range is requested

## Behavior

The order is:

1. Configure the SMU.
2. Read back source/measure settings.
3. Save `configured_*_smu_readback` and `configured_*_smu_readback_check`.
4. If readback exists and does not match, raise `SafetyLimitError`.
5. Enable output only after the check passes.

Readback-unavailable instruments are recorded as `available: false` and are not
blocked. Keithley 2450 and fake SMUs provide readback, so mismatches are blocked
before `output_on`.

## Hardware Use

For lab-laptop runs, inspect `metadata.json` after any stopped run. If
`triggered_limit` ends with `_smu_config_readback`, the output was blocked
before enabling. Fix the recipe or instrument setting/readback query before
attempting a broader dual-gate or lock-in scan.
