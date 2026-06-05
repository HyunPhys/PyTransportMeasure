# Phase 25bp: Hall Workflow Module Split

## What Changed

- Moved Hall workflow orchestration helpers out of `pytransport/cli.py`.
- Added `pytransport/hall_workflow.py`.
- Kept CLI commands as thin wrappers around reusable core helpers.

## Moved Helpers

- `run_dual_gate_lockin_hall_suite_approved_next_scan_rehearsal`
- `inspect_dual_gate_lockin_hall_suite_workflow_status`
- `format_dual_gate_lockin_hall_suite_workflow_status`
- package manifest, rehearsal recipe, fake-instrument, and report helpers

## Why

The Hall workflow now spans package creation, rehearsal, intake, analysis,
review, proposal, approval, and lab handoff. Keeping that orchestration in the
CLI would make future GUI/API reuse harder and would grow the CLI into a large
procedural script. This split keeps measurement workflow logic in a normal
module while preserving the existing commands.

## Behavior

No command behavior was intentionally changed. The existing commands still work:

```powershell
ptm dual-gate-lockin-hall-suite-approved-next-scan-rehearse data\hall_packages\<approved_next_package>
ptm dual-gate-lockin-hall-suite-status data\hall_packages\<approved_next_package>
```

## Verification

- `python -m pytest tests\test_hall_suite_template.py -q`
- `python -m pytransport.cli dual-gate-lockin-hall-suite-status --help`
- `python -m pytest -q`
