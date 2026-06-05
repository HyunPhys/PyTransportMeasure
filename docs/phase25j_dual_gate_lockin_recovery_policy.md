# Phase 25j: Dual-Gate Lock-In Recovery Policy

This phase makes the guarded dual-gate lock-in active sweep safer to debug on
real hardware by recording explicit recovery metadata. It does not implement
automatic resume.

## Scope

- Add checkpoint metadata to `dual_gate_lockin_sweep` runs.
- Record planned, written, and remaining point counts.
- Record the last completed gate-grid point.
- Classify exits as `completed`, `safety_stop`, `interrupted`, or `exception`.
- Keep both gate outputs off after every exit path.
- Add a `Recovery` section to the dual-gate lock-in report.

## Recovery Policy

Current policy is manual review plus restart from the beginning. This is
intentional for early hardware work because gate leakage, lock-in phase, and
SR860 excitation wiring need operator review after any abnormal stop.

If `abort_class` is `safety_stop`, do not resume until the leakage/compliance
cause has been reviewed.

## Metadata Fields

The active sweep metadata now includes:

- `planned_points`
- `points_written`
- `remaining_points`
- `abort_class`
- `last_completed_index`
- `last_completed_gate1_index`
- `last_completed_gate2_index`
- `last_completed_gate1_voltage_v`
- `last_completed_gate2_voltage_v`
- `next_point_index`
- `resume_policy`
- `recovery_recommendation`
- `outputs_off_after_run`

## Lab Checklist

```powershell
ptm dual-gate-lockin-plan configs/recipes/dual_gate_lockin_limited_active.yaml
ptm dual-gate-lockin configs/recipes/dual_gate_lockin_limited_active.yaml --allow-active-sweep --max-hardware-points 4 --progress --plot --report --gate-stats
```

- Confirm `metadata.json` has `abort_class: completed`.
- Confirm `planned_points: 4`, `points_written: 4`, and `remaining_points: 0`.
- Confirm `outputs_off_after_run: true`.
- Confirm `dual_gate_lockin_report.md` contains `## Recovery`.
- For any non-completed run, inspect `triggered_limit`, `error_type`, and
  `recovery_recommendation` before attempting another run.
