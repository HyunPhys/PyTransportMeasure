# Phase 25ad: Accepted-Run Scale-Up Recipe Template

This phase adds a command for creating a candidate broader dual-gate lock-in
recipe from an accepted limited run.

## Command

```powershell
ptm dual-gate-lockin-scale-up-template data\raw\<accepted_limited_run_folder> configs/recipes/dual_gate_lockin_3x3_candidate.yaml --gate1-start-v -0.1 --gate1-stop-v 0.1 --gate1-points 3 --gate2-start-v -0.1 --gate2-stop-v 0.1 --gate2-points 3 --measurement-name dual_gate_lockin_3x3_candidate
```

The command:

- reads the accepted run `metadata.json`,
- copies the saved dual-gate lock-in recipe snapshot,
- updates only the requested gate1/gate2 grid and optional output fields,
- writes a candidate YAML recipe,
- immediately runs the hardware-free scale-up check.

## Why

Broader Hall-bar scans should not require manually copying topology, SR860
settings, Keithley settings, compliance, and safety metadata. Manual copying is
an easy way to create a recipe that looks similar but is not valid evidence
from the accepted limited run.

## Behavior

If the generated recipe is compatible, the command exits with code 0 and prints
both acceptance and scale-up compatibility PASS blocks. If the generated grid no
longer contains the accepted previous points, or another setting changed in an
incompatible way, the command leaves the recipe file in place but exits with
code 2 so it can be inspected before use.

## Lab Checklist

- Generate a candidate recipe from the accepted limited run.
- Confirm the command prints `Dual-gate lock-in scale-up compatibility: PASS`.
- Open the candidate YAML and review only the gate grid, measurement name, and
  output directory before a raised-point hardware run.
