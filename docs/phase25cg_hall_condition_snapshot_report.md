# Phase 25cg: Hall Run Condition Snapshot Report

Added a lab-notebook condition snapshot command:

```powershell
ptm dual-gate-lockin-hall-suite-condition-snapshot data\hall_packages\<package>
```

The command reads `result_intake.json` and returned run metadata, then writes:

- `condition_snapshot_report.md`
- `condition_snapshot.json`

The report compares Vxx/+B/-B/0B settings side by side:

- Keithley gate1/gate2 address and terminal
- Keithley voltage/current ranges
- Keithley NPLC
- Keithley current compliance and source delay
- Keithley readback match status
- SR860 sensitivity/time-constant indices
- SR860 read settle/time constant
- SR860 readback availability and match status

This is a human-readable companion to the drift guard. The drift guard decides
PASS/FAIL; the snapshot makes the measurement conditions easy to inspect in the
lab notebook.

## Lab Checklist

- [ ] Run result intake first.
- [ ] Run `ptm dual-gate-lockin-hall-suite-condition-snapshot <package>`.
- [ ] Attach or paste `condition_snapshot_report.md` into the lab notebook.
- [ ] Confirm Vxx/+B/-B/0B NPLC, ranges, compliance, and SR860 settings are the
  intended values before Hall analysis.
