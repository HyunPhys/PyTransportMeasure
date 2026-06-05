# Phase 44: Lab Context Metadata

## Goal

Make saved runs easier to connect back to the physical lab context: cooldown,
contact geometry, contact notes, and lab notebook references.

## Implemented

- Extended recipe `experiment` metadata with optional fields:
  - `cooldown_id`
  - `contact_geometry`
  - `contact_notes`
  - `lab_notebook_ref`
- Added these fields to the GUI Drain I-V form.
- Preserved the fields through `YAML -> Form` and `Form -> YAML`.
- Added starter template support through `ptm new-recipe` options:
  - `--cooldown-id`
  - `--contact-geometry`
  - `--contact-notes`
  - `--lab-notebook-ref`
- Included context fields in validation reports and Markdown run reports.
- Added `cooldown_id`, `contact_geometry`, and `lab_notebook_ref` to run-index
  records for future search/filter UI work.

## Design Notes

These fields are metadata only. They do not change instrument configuration,
sweep points, safety limits, or runner behavior.

The fields live under the existing `experiment` block so every future method can
reuse the same metadata structure. This keeps the path open for 4-probe,
lock-in, pulse, and multi-instrument runs without adding method-specific lab
notebook fields.

## User Checklist

- [ ] Open `ptm-gui`.
- [ ] In `Measurement > Drain I-V Form`, fill `Cooldown`, `Contact geometry`,
  `Contact notes`, and `Notebook ref`.
- [ ] Click `Form -> YAML`.
- [ ] Confirm the YAML `experiment` block contains the four context fields.
- [ ] Click `YAML -> Form` and confirm the values return to the form.
- [ ] Run a dry-run and open the report.
- [ ] Confirm the report lists cooldown, contact geometry, contact notes, and
  lab notebook reference.
- [ ] From CLI, create a starter recipe with:

  ```powershell
  ptm new-recipe configs/recipes/context_test.yaml --measurement-name context_test --cooldown-id cd-1 --contact-geometry "2-probe wirebond" --lab-notebook-ref "ELN-1 p.2"
  ```

- [ ] Run `ptm validate configs/recipes/context_test.yaml` and confirm the
  context appears in the validation output.
