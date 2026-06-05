# Phase 25m: Dual-Gate Lock-In Hardware Threshold Audit

This phase makes raised dual-gate lock-in hardware point guards explicit and
traceable.

Later policy note: Phase 25y strengthens this rule. Raised hardware point guards
now require both this approval note and `--accepted-previous-run` pointing to a
strict audit PASS artifact.

## Scope

- Keep the default guarded active-sweep threshold at 9 points.
- Require `--hardware-approval-note` whenever `--max-hardware-points` is raised
  above the default.
- Save hardware guard metadata after hardware-path runs:
  - `default_max_hardware_points`
  - `requested_max_hardware_points`
  - `recipe_points`
  - `raised_above_default`
  - `approval_note`

## Policy

Raising `--max-hardware-points` is allowed only as an explicit operator action.
The approval note should capture the immediate lab reason, for example:

```text
2x2 smoke passed, leakage < 10 pA, SR860 readback matched, expanding to 5x5
```

This phase does not decide the first broader scan size. That remains a lab
feedback decision after limited active sweep artifacts have been reviewed.

## Lab Checklist

```powershell
ptm dual-gate-lockin configs/recipes/dual_gate_lockin_limited_active.yaml --allow-active-sweep --max-hardware-points 12 --hardware-approval-note "limited sweep passed; testing raised guard" --progress --plot --report --gate-stats
```

- Confirm the command refuses a raised point guard without
  `--hardware-approval-note`.
- Confirm `metadata.json` records the `hardware_guard` block.
- Confirm `approval_note` matches the lab reason used at execution time.
