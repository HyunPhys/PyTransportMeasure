# Phase 25am: Scale-Up Review Packet

This phase makes the broader dual-gate lock-in candidate workflow more
operator-ready without enabling hardware automatically.

## What Changed

`ptm dual-gate-lockin-scale-up-template` now writes two artifacts:

- the candidate broader recipe YAML,
- a companion review markdown file.

The default review path is the candidate recipe path with `.review.md`.

The review file contains:

- accepted previous run path,
- candidate recipe path,
- candidate point count,
- suggested `--max-hardware-points`,
- hardware-free scale-up check command,
- preflight command,
- hardware run command template,
- full candidate plan,
- lab checklist.

## Why

The actual first broader Hall-bar scan still belongs on the lab laptop after
feedback from a limited active run. This phase reduces manual command assembly
and copy errors when moving from a strict accepted 2x2 run to a candidate 3x3
or 5x5 scan.

## Checklist

- [ ] Generate a candidate recipe from a strict accepted run.
- [ ] Open the generated `.review.md`.
- [ ] Confirm candidate point count and gate grid.
- [ ] Run the hardware-free scale-up check command from the review file.
- [ ] Run preflight from the review file.
- [ ] Edit the approval note before running the hardware command.

