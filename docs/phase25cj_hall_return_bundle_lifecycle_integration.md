# Phase 25cj: Hall Return Bundle Lifecycle Integration

The Hall package lifecycle now includes the package-local return bundle index.

After a returned Hall suite has been intaked, condition-audited, analyzed,
reviewed, and given a next-scan proposal, write the return bundle index:

```powershell
ptm dual-gate-lockin-hall-suite-lifecycle-status data\hall_packages\<package> --json-output data\hall_packages\<package>\lifecycle_status.json
ptm dual-gate-lockin-hall-suite-return-bundle-index data\hall_packages\<package> --overwrite
ptm dual-gate-lockin-hall-suite-lifecycle-status data\hall_packages\<package>
```

Expected final lifecycle state:

```text
Lifecycle state: return_bundle_archived
```

The `Return bundle index` lifecycle stage passes only when
`return_bundle/return_bundle_index.json` exists and its
`missing_artifact_count` is zero.

## Lab Checklist

- [ ] Confirm the package has passed intake, condition snapshot, condition drift,
  Hall analysis, review, and next-scan proposal.
- [ ] Write the return bundle index.
- [ ] Rerun lifecycle status.
- [ ] Confirm `Return bundle index` is `PASS`.
- [ ] Confirm lifecycle state is `return_bundle_archived`.
- [ ] Attach `return_bundle/return_bundle_index.md` to the lab notebook.
