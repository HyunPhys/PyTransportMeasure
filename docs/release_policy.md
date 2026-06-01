# Release Policy

PyTransportMeasure releases should make lab work reproducible. A release tag
should answer: which code produced which measurement artifacts?

## Versioning

Use tags like `v0.1.0`.

- Patch: fixes, docs, small validation improvements.
- Minor: new user-facing commands, measurement methods, GUI features, or
  artifact schema additions.
- Major: breaking recipe, metadata, CLI, or hardware-control behavior changes.

## Release Checklist

Before tagging:

```powershell
python -m pytest
ptm --help
```

For GUI releases:

```powershell
pip install -e ".[gui,test]"
ptm-gui
```

Confirm:

- [ ] `.gitignore` excludes `data/`, local instrument manuals, build outputs,
  and caches.
- [ ] `README.md` describes the current supported workflows.
- [ ] `docs/roadmap.md` marks completed phases.
- [ ] `CHANGELOG.md` has an entry for the release.
- [ ] Hardware-enabled paths have matching checklists.
- [ ] Hardware-blocked paths say they are blocked.

## First GitHub Release

Recommended first tag:

```powershell
git tag -a v0.1.0 -m "PyTransportMeasure v0.1.0"
git push origin main
git push origin v0.1.0
```

Use the `CHANGELOG.md` `v0.1.0` section as the GitHub release notes.
