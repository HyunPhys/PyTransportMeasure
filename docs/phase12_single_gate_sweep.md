# Phase 12 Single-Gate Sweep Core

Single-gate sweep adds the first two-SMU measurement path. It is intentionally
small: one gate voltage loop, one Drain I-V inner loop, CSV/JSON saving, dry-run
simulation, and conservative shutdown on any compliance or software current
limit.

This phase is ready for dry-run validation. Hardware use requires two separate
Keithley 2450 resources, one wired as drain and one wired as gate.

## Recipe

Example:

```powershell
configs\recipes\single_gate_dry_run.yaml
```

The recipe has separate instrument blocks:

```yaml
drain_instrument:
  id: keithley_2450
  address: GPIB0::2::INSTR

gate_instrument:
  id: keithley_2450
  address: GPIB0::3::INSTR
```

And separate sweeps:

```yaml
gate_sweep:
  start_v: -0.5
  stop_v: 0.5
  points: 5
  settle_s: 0.0
  current_compliance_a: 1.0e-8

drain_sweep:
  mode: linear_one_way
  start_v: -0.1
  stop_v: 0.1
  points: 11
  delay_s: 0.0
  current_compliance_a: 1.0e-6
```

Only the Drain sweep is nested inside each gate point. The output is one
long-form `points.csv`.

## Commands

Preview without hardware:

```powershell
ptm single-gate-plan configs\recipes\single_gate_dry_run.yaml
```

Dry-run:

```powershell
ptm single-gate configs\recipes\single_gate_dry_run.yaml --dry-run --progress --fake-channel-resistance-ohm 1000000 --fake-noise-std-a 0
```

Hardware run:

```powershell
ptm single-gate configs\recipes\single_gate_dry_run.yaml
```

For hardware, edit `drain_instrument.address` and `gate_instrument.address`
first. They must be different resources.

## Output

The run folder contains:

```text
points.csv
metadata.json
recipe_snapshot.yaml
safety_snapshot.yaml
```

`points.csv` columns:

- `gate_voltage_v`
- `drain_voltage_v`
- `drain_current_a`
- `gate_current_a`
- `drain_resistance_ohm`
- `drain_compliance_hit`
- `gate_compliance_hit`

## Safety Behavior

- Gate and drain voltage ranges are both checked against the selected safety
  preset.
- Gate and drain compliance values are both checked against the selected safety
  preset.
- Gate compliance stops immediately.
- Drain compliance stops immediately.
- Software current limits stop immediately.
- Both outputs are turned off in normal completion, safety stop, error, or
  interrupt paths.
- Partial CSV and metadata are still saved.

## Smoke-Test Checklist

```powershell
python -m pytest
ptm single-gate-plan configs\recipes\single_gate_dry_run.yaml
ptm single-gate configs\recipes\single_gate_dry_run.yaml --dry-run --progress --fake-channel-resistance-ohm 1000000 --fake-noise-std-a 0
```

Expected dry-run result:

- plan shows `Total points: 55`
- run prints 55 progress lines if `--progress` is used
- `Metadata completed: True`
- `points.csv` has 55 data rows
- `metadata.json` has `measurement_type: single_gate_sweep`
- no VISA or Keithley communication occurs in dry-run
