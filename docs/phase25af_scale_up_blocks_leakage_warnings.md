# Phase 25af: Scale-Up Blocks Leakage Warnings

This phase connects the dual-gate lock-in leakage-margin audit to the scale-up
gate used before broader hardware scans.

## Scope

The acceptance audit still treats leakage/compliance margin below 10x as a
warning when no compliance limit was hit. That keeps the saved run review useful
without rewriting history as a hard failure.

For scale-up decisions, the policy is stricter:

- `ptm dual-gate-lockin-scale-up-check` fails if the accepted previous run has a
  gate leakage warning,
- raised-point `ptm dual-gate-lockin ... --allow-active-sweep` fails before
  preflight or output if `--accepted-previous-run` has a gate leakage warning,
- the blocking message lists the warning and asks for another limited run or a
  leakage fix before increasing scan size.

## Lab Policy

Use a limited active sweep as evidence for a broader scan only when all are true:

- the strict acceptance audit passes,
- SR860 settings match the recipe,
- both Keithley gate source blocks have explicit voltage range, current range,
  and NPLC,
- both gate leakage/compliance margins are comfortably above 10x,
- the previous gate grid is contained in the candidate broader grid.

## Checklist

- Run `ptm dual-gate-lockin-audit data\raw\<limited_run> --write-report`.
- Confirm no `gate1_leakage_margin` or `gate2_leakage_margin` warning appears.
- Run `ptm dual-gate-lockin-scale-up-check data\raw\<limited_run> configs\recipes\<candidate>.yaml`.
- Continue to a raised-point hardware run only if the scale-up check prints
  `Dual-gate lock-in scale-up compatibility: PASS`.
