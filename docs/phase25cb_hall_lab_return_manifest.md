# Phase 25cb: Hall Package Lab-Return Manifest

## Summary

Added a package-local manifest for run folders returned from the lab laptop after
Hall-suite acquisition and result intake:

```powershell
ptm dual-gate-lockin-hall-suite-lab-return-manifest data\hall_packages\<package> --operator-note "<lab notebook reference>" --overwrite
```

## Outputs

- `lab_return/lab_return_manifest.md`
- `lab_return/lab_return_manifest.json`

## Recorded Fields

- package directory and package manifest path
- SHA256 of `package_manifest.json`
- package ZIP path and SHA256 when available
- `result_intake.json` path
- intake accepted status and issue count
- returned run folders for Vxx, +B Vxy, -B Vxy, and optional 0B Vxy
- operator note or lab notebook reference
- `ready_for_analysis`

## Lab Checklist

- [ ] Run result intake after the lab laptop returns run folders.
- [ ] Confirm result intake reports PASS.
- [ ] Run the lab-return manifest command.
- [ ] Attach `lab_return_manifest.md` to the lab notebook or package archive.
- [ ] Continue to Hall analysis only if `Ready for analysis: True`.
