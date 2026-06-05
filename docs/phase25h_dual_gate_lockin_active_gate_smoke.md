# Phase 25h: Dual-Gate Lock-In Active-Gate Smoke

This phase adds the first guarded dual-gate lock-in command that can enable
Keithley gate outputs.

## Command

```powershell
ptm dual-gate-lockin-active-smoke configs/recipes/dual_gate_lockin_dry_run.yaml --gate1-v 0.01 --gate2-v 0 --samples 3 --settle-s 0.2 --interval-s 0.2 --progress
```

Use `--dry-run` to exercise the same file-writing path without hardware output.

## Safety Boundary

The command:

- prints the topology and requested static gate voltages
- runs the three-instrument dual-gate lock-in preflight
- asks for confirmation unless `--yes` is provided
- configures both Keithley gates with the recipe compliance, ranges, terminal,
  and NPLC
- sets one static gate1/gate2 voltage pair
- records gate leakage and SR860 X/Y/R/theta samples
- turns both gate outputs off after completion, safety stop, error, or interrupt

It does not run a 2D gate sweep.

## Artifacts

- `active_gate_smoke.csv`
- `metadata.json`
- recipe and safety snapshots

The metadata records `outputs_off_after_run: true` and
`gate_outputs_enabled: false` after cleanup.

## Next Step

After lab confirmation on a safe test device, the next phase can implement a
tiny bounded active dual-gate lock-in sweep.
