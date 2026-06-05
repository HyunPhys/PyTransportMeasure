# Phase 25chb: Hall Topology Condition Audit

## Summary

This phase makes Hall-bar contact topology part of the returned-run condition
snapshot and condition-drift guard.

The Hall suite condition snapshot now includes a `Hall-Bar Topology` table with
each returned run's voltage-probe role, magnetic field, excitation contacts,
SR860 voltage contacts, channel geometry, bias resistor, and topology layout.

The condition-drift audit now compares the returned run recipe snapshot against
the packaged recipe for topology fields including:

- `topology.voltage_probe_role`
- `topology.lockin_input_contacts`
- `topology.excitation_contacts`
- `topology.source_contact`
- `topology.drain_contact`
- `topology.magnetic_field_t`
- `topology.channel_length_m`
- `topology.channel_width_m`
- `topology.bias_resistor_ohm`
- `topology.topology_layout`

## Why This Matters

For Hall-bar graphene measurements, Keithley NPLC/range/compliance and SR860
settings are not the only reproducibility conditions. A Vxx/Vxy contact swap or
changed excitation contact pair changes the meaning of the data even when all
instrument settings still match. The drift guard now treats that as a
measurement-condition change before Hall analysis is allowed.

## Lab Checklist

- [ ] Run `ptm dual-gate-lockin-hall-suite-condition-snapshot ...`.
- [ ] Confirm the `Hall-Bar Topology` table shows the expected Vxx and Vxy
  contact pairs.
- [ ] Run `ptm dual-gate-lockin-hall-suite-condition-drift ...`.
- [ ] Confirm no `topology.*` drift issues appear.
- [ ] Treat any topology drift as a stop for Hall analysis until the package or
  returned run assignment is corrected.
