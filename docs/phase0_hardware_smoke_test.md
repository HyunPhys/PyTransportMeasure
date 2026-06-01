# Phase 0 Hardware Smoke Test

Phase 0 proves the smallest useful hardware loop:

1. Load a YAML Drain I-V recipe.
2. Configure one Keithley 2450 in SCPI mode.
3. Sweep drain voltage point-by-point.
4. Measure current.
5. Save `points.csv` and `metadata.json`.
6. Summarize and plot the saved run.

## Verified Hardware

- Instrument: Keithley 2450 SourceMeter
- VISA address used during development: `GPIB0::2::INSTR`
- Command set: `SCPI`
- Test load: `1 kOhm` resistor
- Smoke-test recipe: `configs/recipes/drain_iv_1k_resistor.yaml`
- Safety preset: `configs/safety/resistor_1k_check.yaml`
- Terminal in recipe: `FRONT`
- Voltage range in recipe: `0.2 V`
- Current range in recipe: `200 uA`

## Phase 0 Acceptance Checklist

Run these from the project root.

```powershell
pip install -e ".[test]"
python -m pytest
ptm list-resources
ptm probe --instrument keithley_2450 --address "GPIB0::2::INSTR"
ptm validate configs/recipes/drain_iv_1k_resistor.yaml
ptm run configs/recipes/drain_iv_1k_resistor.yaml --summary --plot
ptm summarize data\raw\<run_folder>
ptm plot data\raw\<run_folder>
```

Expected results:

- `python -m pytest` passes.
- `ptm list-resources` includes `GPIB0::2::INSTR`.
- `ptm probe` reports `language: SCPI`.
- `ptm probe` reports no pending system error.
- `ptm validate` reports `Recipe validation: OK`.
- `ptm run` reports `Metadata completed: True`.
- `points.csv` has 21 measurement points.
- `ptm summarize` reports fitted resistance near `1000 ohm`.
- `ptm plot` creates `iv_plot.svg`.
- Keithley output is off after the run.

## Commands Implemented In Phase 0

```powershell
ptm list-resources
ptm identify --instrument keithley_2450 --address "GPIB0::2::INSTR"
ptm probe --instrument keithley_2450 --address "GPIB0::2::INSTR"
ptm validate configs/recipes/drain_iv_1k_resistor.yaml
ptm run configs/recipes/drain_iv_1k_resistor.yaml --summary --plot
ptm summarize data\raw\<run_folder>
ptm plot data\raw\<run_folder>
```

## Notes Before Real Devices

The active smoke-test recipe is designed for a 1 kOhm resistor and allows up to
`500 uA` software current. Before connecting a real nanodevice, switch to:

```powershell
ptm run configs/recipes/drain_iv_nanodevice_safe.yaml
```

Then review the voltage range, compliance current, and safety preset manually.
