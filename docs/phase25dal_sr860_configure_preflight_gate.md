# Phase 25dal: SR860 Configure Preflight Gate

## Summary

This phase lets lock-in preflight require a saved SR860 configure transcript:

```powershell
ptm ac-lockin-preflight configs\recipes\ac_lockin_hardware_smoke.yaml --sr860-configure-json docs\sr860_configure.json
ptm dual-gate-lockin-preflight configs\recipes\dual_gate_lockin_four_terminal_dry_run.yaml --sr860-configure-json docs\sr860_configure.json
```

The option is deliberately opt-in. Existing preflight commands still behave the
same way when no configure JSON is supplied.

## Behavior

When `--sr860-configure-json` is present, preflight:

- loads the saved configure transcript
- verifies it against the current recipe using the same checker as
  `ptm sr860-configure-check`
- prints the evidence check in the preflight report
- marks preflight not OK if the configure evidence is stale, incomplete, or
  mismatched

This keeps SR860 setting writes separate from measurement runners, while still
allowing the lab operator to make stale configuration evidence block hardware
work.

## Lab Checklist

- [ ] Run `ptm sr860-configure ... --json-output docs\sr860_configure.json`.
- [ ] Run preflight with `--sr860-configure-json docs\sr860_configure.json`.
- [ ] Confirm both live `Lock-in setting check` and `SR860 configure evidence
      check` report OK.
- [ ] If either check fails, do not enable SMU output.
