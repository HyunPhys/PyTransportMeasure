# Phase 25bi: Hall-Suite Analysis Orchestration

This phase adds a single command that runs the Hall analysis chain after result
intake has passed.

## What Changed

- Added `ptm dual-gate-lockin-hall-suite-analyze`.
- The command accepts a package folder or `result_intake.json`.
- It refuses to run unless `result_intake.json` has `accepted: true`.
- It writes:
  - `hall_analysis/antisym/hall_antisym.csv`
  - `hall_analysis/antisym/hall_antisym_report.md`
  - `hall_analysis/zero_corrected/hall_zero_corrected.csv`, when a 0B run is
    available
  - `hall_analysis/zero_corrected/hall_zero_corrected_report.md`, when a 0B run
    is available
  - `hall_analysis/mobility/hall_mobility.csv`
  - `hall_analysis/mobility/hall_mobility_report.md`
  - `hall_analysis/hall_suite_analysis_manifest.json`
  - `hall_analysis/hall_suite_analysis_report.md`
- By default, mobility uses zero-corrected Hall density when a zero-field run is
  present.
- `--prefer-antisym-density` forces mobility to use antisymmetrized Hall density
  even when zero-field correction was written.

## Example

```powershell
ptm dual-gate-lockin-hall-suite-analyze data\hall_packages\<sample_lab_package>
```

Force antisymmetrized density for mobility:

```powershell
ptm dual-gate-lockin-hall-suite-analyze data\hall_packages\<sample_lab_package> --prefer-antisym-density --overwrite
```

## Lab Checklist

- [ ] Run `ptm dual-gate-lockin-hall-suite-intake` first.
- [ ] Confirm intake PASS.
- [ ] Run `ptm dual-gate-lockin-hall-suite-analyze`.
- [ ] Confirm antisym, zero-corrected if applicable, and mobility artifacts are
  written.
- [ ] Open `hall_suite_analysis_manifest.json` and confirm the density source is
  the intended one.

## Verification

- `python -m pytest tests\test_hall_suite_template.py -q`
- `python -m pytransport.cli dual-gate-lockin-hall-suite-analyze --help`
