# Phase 25bg: Hall-Suite Acquisition Package

This phase adds a portable, hardware-free package for running an adjusted
Hall-bar dual-gate lock-in suite on the lab laptop.

## What Changed

- Added `ptm dual-gate-lockin-hall-suite-package`.
- The command checks the input Vxx/+B Vxy/-B Vxy/0B Vxy suite before packaging.
- It copies the suite recipes into `recipes/`.
- It writes `acquisition_runbook.md` with:
  - suite consistency check
  - suite plan
  - suite chunk plan
  - per-recipe plan and preflight commands
  - guarded chunk acquisition templates
  - chunk feedback and suite-adjustment loop
  - stitching commands
  - Hall antisymmetry, zero-field correction, and mobility commands
- It writes `package_manifest.json`.
- It creates a ZIP next to the package folder.
- It can include chunk feedback files, saved preflight text, and lab note files.

## Example

```powershell
ptm dual-gate-lockin-hall-suite-package configs\recipes\<adjusted_suite>\<prefix>_vxx.yaml configs\recipes\<adjusted_suite>\<prefix>_vxy_plus_b.yaml configs\recipes\<adjusted_suite>\<prefix>_vxy_minus_b.yaml data\hall_packages --zero-field-recipe configs\recipes\<adjusted_suite>\<prefix>_vxy_zero_b.yaml --package-name <sample_lab_package> --chunk-size <N> --max-hardware-points <N> --acquisition-note "<lab handoff note>"
```

Optional attached files:

```powershell
ptm dual-gate-lockin-hall-suite-package ... --chunk-feedback-file docs\<sample>_chunk_feedback.md --preflight-file docs\<sample>_preflight.txt --note-file docs\<sample>_lab_notes.md --overwrite
```

## Lab Checklist

- [ ] Confirm the package command exits successfully.
- [ ] Confirm the package folder contains `recipes/`, `acquisition_runbook.md`,
  and `package_manifest.json`.
- [ ] Confirm the ZIP exists next to the package folder.
- [ ] Open `acquisition_runbook.md` and verify the chunk size, hardware point
  limit, accepted previous run placeholder, and analysis commands.
- [ ] On the lab laptop, run the suite check and preflight commands from the
  runbook before enabling output.

## Verification

- `python -m pytest tests\test_hall_suite_template.py -q`
- `python -m pytransport.cli dual-gate-lockin-hall-suite-package --help`
