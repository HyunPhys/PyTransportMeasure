# Phase 25dao: Hardware Evidence Metadata

## Summary

Guarded lock-in hardware commands now record which evidence files were supplied
before the run. When a command uses `--measurement-audit-json` or
`--sr860-configure-json`, successful hardware runs write a top-level
`hardware_evidence` block to `metadata.json`.

Example:

```json
{
  "hardware_evidence": {
    "schema": "pytransport.hardware_evidence.v1",
    "measurement_audit_json": "docs/sample_measurement_audit.json",
    "measurement_audit_evidence_passed": true,
    "sr860_configure_json": "docs/sr860_configure.json",
    "sr860_configure_evidence_passed": true,
    "preflight_reran_after_evidence_check": true
  }
}
```

Dry-runs do not write this block.

## Why This Matters

For Hall-bar graphene scans, the run folder should say not only what the recipe
contained, but also which pre-run evidence was checked before output/readout.
This makes later lab-notebook review and acquisition-condition drift debugging
more direct.

## Lab Checklist

- [ ] Pass `--measurement-audit-json` to guarded lock-in hardware commands when
      using saved measurement-condition evidence.
- [ ] Pass `--sr860-configure-json` when the run depends on a prior guarded
      SR860 configure transcript.
- [ ] After the run, confirm `metadata.json.hardware_evidence` records the paths
      used for that run.
- [ ] Treat missing `hardware_evidence` on a real lock-in hardware run as a sign
      that evidence gating was not requested for that command.
