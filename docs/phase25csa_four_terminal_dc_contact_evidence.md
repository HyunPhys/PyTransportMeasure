# Phase 25csa: Four-Terminal DC Contact Evidence Hardening

## Summary

This phase strengthens the four-terminal DC measurement path without pretending
that new lab feedback has already arrived.

Dry-run and guarded active four-terminal DC metadata now carry a normalized
`contact_topology` block in addition to the recipe `contact_map`. The lab smoke
intake checks that the force contacts, sense contacts, and terminal plane are
present, distinct, separated, and consistent before accepting a run.

## Metadata Added

Four-terminal DC run metadata now records:

- `contact_topology.force_contacts`
- `contact_topology.sense_contacts`
- `contact_topology.terminal_plane`
- `contact_topology.contacts_are_distinct`
- `contact_topology.force_and_sense_contacts_separated`
- `contact_topology.terminal_plane_matches_instrument`

The command-review evidence check also confirms that the dry-run metadata
preserved this contact topology before an active runner can use the command
review JSON.

## Lab Checklist

- [ ] Run a dry-run and confirm `metadata.json` has `contact_topology`.
- [ ] Confirm `force_contacts` and `sense_contacts` match the real fixture.
- [ ] Run the guarded active smoke only after preflight and command review pass.
- [ ] Run `ptm four-terminal-dc-lab-smoke-intake ...`.
- [ ] Confirm the intake prints `Contact topology OK: True`.
- [ ] Confirm the intake prints the expected force and sense contact pairs.
- [ ] Treat any contact-topology intake failure as a wiring/recipe review stop,
  even if NPLC/range/readback checks pass.
