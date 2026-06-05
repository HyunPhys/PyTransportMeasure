# Phase 25as: Hall-Bar Recipe Suite Template

## Goal

Create a consistent measurement recipe set for Hall-bar dual-gate lock-in
experiments from one verified base recipe.

This reduces manual YAML drift between:

- longitudinal Vxx
- Hall Vxy at `+B`
- Hall Vxy at `-B`
- optional Hall Vxy at `B=0`

## Command

```powershell
ptm dual-gate-lockin-hall-suite-template configs\recipes\<base_dual_gate_lockin_recipe>.yaml configs\recipes\<hall_suite_dir> --measurement-prefix <sample_device> --magnetic-field-t <B_abs_T> --longitudinal-contact Vxx+ --longitudinal-contact Vxx- --hall-contact Vxy+ --hall-contact Vxy- --channel-length-m <L_m> --channel-width-m <W_m>
```

Use `--no-zero-field` to skip the `B=0` recipe.

## Outputs

For prefix `sampleA`, the command writes:

- `sampleA_vxx.yaml`
- `sampleA_vxy_plus_b.yaml`
- `sampleA_vxy_minus_b.yaml`
- `sampleA_vxy_zero_b.yaml`, unless skipped
- `sampleA_review.md`

The generated recipes share the base recipe's Keithley gate settings, SR860
settings, gate grid, safety preset, topology excitation path, and output policy.
Only the measurement name, voltage probe role, voltage contacts, longitudinal
channel dimensions, and magnetic-field metadata are changed.

## Review Markdown

The review file contains:

- plan commands for each generated recipe
- preflight commands for each generated recipe
- guarded hardware command templates
- Hall antisymmetry, zero-field correction, and mobility analysis command
  templates
- short plan snapshots for Vxx and Vxy

## Hardware Boundary

This command only writes YAML and markdown. It does not run preflight, configure
SR860, enable Keithley outputs, or relax the active sweep guards.
