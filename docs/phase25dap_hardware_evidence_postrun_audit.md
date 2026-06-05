# Phase 25dap: Hardware Evidence Post-Run Audit

## Summary

This phase adds a post-run audit for `metadata.json.hardware_evidence`.

The audit checks whether a saved run records the evidence files used before
hardware output/readout, and can recompute the saved measurement-parameter audit
against the current recipe path.

## Command

```powershell
ptm hardware-evidence-audit data\raw\<run_folder> --require-measurement-audit --json-output docs\hardware_evidence_audit.json
```

Optional strict gates:

- `--require-measurement-audit`
- `--require-sr860-configure`

## What It Checks

- `metadata.hardware_evidence` exists when required.
- `hardware_evidence.schema` is `pytransport.hardware_evidence.v1`.
- `preflight_reran_after_evidence_check` is true.
- saved measurement-audit JSON exists.
- saved measurement-audit JSON still matches `metadata.recipe_path`, when that
  recipe file is available.
- saved SR860 configure JSON exists and still matches `metadata.recipe_path`,
  when requested and available.

## Lab Checklist

- [ ] Run this audit after guarded AC/dual-gate lock-in hardware runs that used
      evidence files.
- [ ] Save the JSON beside lab notes or package return artifacts.
- [ ] If the audit fails, inspect whether the recipe changed after acquisition
      or whether evidence files were moved.
