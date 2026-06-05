# Phase 25ci: Hall Return Bundle Index

Added a package-local return bundle index:

```powershell
ptm dual-gate-lockin-hall-suite-return-bundle-index data\hall_packages\<package> --overwrite
```

The command writes:

- `return_bundle/return_bundle_index.md`
- `return_bundle/return_bundle_index.json`

The index links the important returned-package artifacts:

- package manifest and acquisition runbook
- handoff summary
- result intake report and JSON
- condition snapshot report and JSON
- condition drift report and JSON
- lab-return manifest
- saved lifecycle status JSON
- Hall analysis report and manifest
- Hall analysis review
- next-scan proposal

This is intended as a lab-notebook table of contents after the Hall suite has
returned from the lab laptop and analysis/proposal artifacts are written.

## Lab Checklist

- [ ] Save lifecycle status into the package folder.
- [ ] Run `ptm dual-gate-lockin-hall-suite-return-bundle-index <package> --overwrite`.
- [ ] Confirm `missing_artifact_count` is 0 for a fully analyzed returned
  package.
- [ ] Attach `return_bundle_index.md` to the lab notebook entry.
