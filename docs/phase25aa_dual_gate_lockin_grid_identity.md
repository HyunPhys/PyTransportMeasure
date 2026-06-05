# Phase 25aa: Dual-Gate Lock-In Grid Identity

This phase adds a stable identity for the ordered dual-gate lock-in scan grid.
It prepares the codebase for broader Hall-bar scans, run comparison, and future
manual resume tooling.

## Scope

Dual-gate lock-in sweep metadata now records:

- `planned_gate_grid`
- `planned_gate_grid_signature`
- `planned_gate_grid_signature_algorithm: sha256_json_v1`

`planned_gate_grid` is the ordered list of gate1/gate2 points exactly as the
runner executes them. The signature is a SHA-256 hash of that ordered JSON grid.

## Why

For 2D Hall-bar scans, `points_written: 17` is not enough context by itself. A
partial or accepted run must also identify which gate-grid definition and order
produced those points. This matters when comparing two runs, deciding whether a
broader scan is a true extension of a limited scan, or later adding manual
resume/restart tooling.

## Acceptance Audit

`ptm dual-gate-lockin-audit` now checks the grid when the metadata is present:

- the saved signature matches `planned_gate_grid`,
- the planned grid length matches `points.csv`,
- each CSV row index, gate indices, and gate voltages match the planned grid.

Older artifacts without grid metadata receive a warning instead of a hard
failure. New accepted artifacts should include the grid metadata before they are
used as evidence for larger hardware scans.

## Lab Checklist

- Run a limited dual-gate lock-in sweep.
- Open `metadata.json` and confirm `planned_gate_grid_signature` exists.
- Confirm `planned_gate_grid[0]` matches the first row of `points.csv`.
- Confirm `planned_gate_grid[-1]` matches the final planned gate point.
- Run `ptm dual-gate-lockin-audit ... --write-report` and confirm no
  `planned_gate_grid` error appears.
