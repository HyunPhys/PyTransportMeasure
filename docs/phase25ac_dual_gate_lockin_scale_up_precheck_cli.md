# Phase 25ac: Dual-Gate Lock-In Scale-Up Pre-Check CLI

This phase adds a hardware-free command for checking whether an accepted
dual-gate lock-in run can justify a candidate broader scan recipe.

## Command

```powershell
ptm dual-gate-lockin-scale-up-check data\raw\<accepted_limited_run_folder> configs/recipes/<candidate_broader_recipe>.yaml
```

The command performs the same two checks used by raised-point hardware runs:

- strict `dual-gate-lockin-audit` on the accepted previous run,
- scale-up compatibility between the accepted run metadata and the candidate
  recipe.

It does not open VISA resources and does not enable hardware output.

## Pass Criteria

The command exits with code 0 only when both blocks pass:

```text
Dual-gate lock-in acceptance: PASS
Dual-gate lock-in scale-up compatibility: PASS
```

If either check fails, the command exits with code 2 and prints the issue list.

## Lab Checklist

- Run this command after a limited active run has passed strict acceptance.
- Review any compatibility issues before editing `--max-hardware-points`.
- Use the same candidate recipe for the later raised-point hardware command.
