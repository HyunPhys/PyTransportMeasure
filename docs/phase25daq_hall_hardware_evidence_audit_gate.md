# Phase 25daq - Hall Suite Hardware Evidence Audit Gate

## Summary

This phase adds a package-level post-run evidence audit for Hall-bar dual-gate
lock-in workflows.

After `dual-gate-lockin-hall-suite-intake` accepts returned Vxx/+B/-B/0B run
folders, run:

```powershell
ptm dual-gate-lockin-hall-suite-hardware-evidence-audits data\hall_packages\<package> --overwrite
```

The command writes:

- `hardware_evidence_audits/hardware_evidence_audits.md`
- `hardware_evidence_audits/hardware_evidence_audits.json`
- per-run hardware evidence audit JSON/Markdown files

## Measurement Relevance

The audit rechecks each returned run's `metadata.hardware_evidence` block. By
default it requires saved measurement-parameter audit evidence, so Keithley
settings such as NPLC, voltage range, current range, compliance, and source
delay are treated as analysis-gating measurement conditions. Use
`--require-sr860-configure` when the run was expected to carry saved SR860
configuration evidence as well.

## Lifecycle Integration

`ptm dual-gate-lockin-hall-suite-lifecycle-status` now includes a
`Hardware evidence audits` stage and reports `hardware_evidence_ready`.
`ready_for_analysis` stays false until this stage passes.

## Lab Checklist

- [ ] Run Hall-suite result intake and confirm it is accepted.
- [ ] Run the package hardware evidence audit command.
- [ ] Confirm `Accepted for analysis gate: True` in the generated Markdown.
- [ ] Rerun lifecycle status and confirm `Hardware evidence audits` is PASS.
- [ ] Continue to condition snapshot, drift audit, lab-return manifest, and Hall
  analysis only after the evidence audit passes.
