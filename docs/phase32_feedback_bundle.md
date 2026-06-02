# Phase 32 - Run Feedback Bundle

This phase adds a portable feedback bundle for lab laptop hardware validation.

## Implemented

- Added `ptm feedback-bundle <run_dir>`.
- Added a GUI `Feedback Bundle` button for the currently loaded run.
- Bundles include copied run artifacts, `inspection.txt`, `environment.json`,
  `quality.txt`, `bundle_manifest.json`, and a ZIP archive.
- Bundles can exclude large point, plot, or report artifacts from the CLI.
- The bundle works for mixed measurement methods through the method registry.

## CLI Workflow

```powershell
ptm feedback-bundle data\raw\<run_folder>
```

Optional size-reduction flags:

```powershell
ptm feedback-bundle data\raw\<run_folder> --no-points
ptm feedback-bundle data\raw\<run_folder> --no-plots --no-reports
```

The command writes:

```text
data/feedback/<timestamp>_<measurement>_feedback/
data/feedback/<timestamp>_<measurement>_feedback.zip
```

## GUI Workflow

1. Run or load a saved run in `ptm-gui`.
2. Click `Feedback Bundle`.
3. Send the generated ZIP for debugging/review.

## Intended Use

The development machine does not need to connect to lab instruments. Hardware
validation can happen on the lab laptop, then the resulting feedback ZIP can be
shared for code/debug iterations.
