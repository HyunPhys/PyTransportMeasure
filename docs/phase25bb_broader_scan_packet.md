# Phase 25bb: Broader Scan Packet

This phase adds a hardware-free lab execution packet for the first broader
dual-gate lock-in hardware scan.

## What Changed

- Added `ptm dual-gate-lockin-broader-scan-packet`.
- The command accepts an accepted previous run and a candidate broader recipe.
- It prints or writes a markdown packet containing:
  - strict accepted-run audit
  - scale-up compatibility audit
  - Keithley measurement parameters, including NPLC, ranges, source delay, and
    compliance
  - SR860 measurement settings summary
  - chunk plan and chunk acquisition commands
  - stitch and strict post-run audit commands

## Usage

```powershell
ptm dual-gate-lockin-broader-scan-packet data\raw\<accepted_run> configs\recipes\<candidate_dual_gate_lockin_recipe>.yaml --chunk-size <N> --max-hardware-points <N> --output docs\<sample>_broader_scan_packet.md
```

## Why It Matters

The broader scan is the point where the program starts moving from smoke tests
toward real Hall-bar graphene mapping. The packet keeps the larger measurement
workflow explicit before hardware output is enabled. NPLC is shown with the
other Keithley settings because it controls current integration time and affects
the speed/noise tradeoff of gate leakage readback.

## Lab Checklist

- `Packet ready for lab execution: yes`
- Keithley gate1/gate2 voltage ranges cover the planned sweeps.
- Keithley gate1/gate2 current ranges and compliance are intentional.
- Keithley gate1/gate2 NPLC values are intentional for the noise/speed tradeoff.
- SR860 preflight readback matches the recipe.
- Each chunk is within `--max-hardware-points`.
- The stitched run passes strict `ptm dual-gate-lockin-audit`.

## Verification

- `python -m pytest tests\test_cli_dual_gate_lockin.py -q`
- `python -m pytransport.cli dual-gate-lockin-broader-scan-packet --help`
- `python -m pytest -q`
- `git diff --check`
