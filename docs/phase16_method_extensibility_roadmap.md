# Phase 16 - Measurement Method Extensibility Roadmap

This phase intentionally does not implement 4-probe, AC, lock-in, or pulse
measurement. The goal is to keep the current verified DC Drain I-V path stable
while recording the design rules and TODO list for adding those methods later.

## Current Boundary

The verified measurement core remains:

- Keithley 2450 DC voltage-source/current-measure Drain I-V
- Dry-run fake SMU path using the same runner and artifact flow
- Single-gate dry-run and scheme composition
- CSV point data plus JSON metadata
- Summary, plot, report, batch, scheme, and campaign review tools

No 4-probe recipe field or driver command is active in this phase.

## Design Rules For Future Methods

New methods should be added by composing small capabilities instead of expanding
one large instrument or runner object.

- Keep recipe schemas method-specific. A Drain I-V recipe should not accumulate
  lock-in, gate, pulse, or remote-sense fields until that capability is actually
  implemented and smoke-tested.
- Keep instrument drivers focused on reusable capabilities, such as source DC
  voltage, measure DC current, configure terminal, configure range, read lock-in
  channels, or arm a pulse. Runners decide how capabilities are combined.
- Keep CLI and GUI thin. They should call recipe loading, planning, runners, and
  artifact generators rather than duplicating measurement logic.
- Keep scheme steps method-level. A scheme should compose "run this Drain I-V" or
  "run this single-gate sweep", not low-level SCPI commands.
- Keep saved artifacts self-describing. Metadata must include
  `measurement_type`, recipe snapshot, safety snapshot, completion state, error
  state, and method-specific acquisition settings.
- Keep analysis dispatch based on `measurement_type` and available columns.
  Existing Drain I-V analysis should not need to know about future lock-in or
  pulse columns.
- Add hardware commands only after manual review and a dry-run or fake-driver
  path exists. Every hardware method needs a small smoke-test checklist before it
  becomes a normal workflow.

## TODO - 4-Probe / Remote Sense

Purpose: support Keithley 2450 4-probe resistance-style measurements after the
DC 2-wire path is fully stable.

Planned work:

- Confirm the exact SCPI command sequence from the 2450 manual for local vs
  remote sense in SCPI mode.
- Decide whether remote sense belongs in a generic source-measure capability
  config or in a method-specific DC resistance / Drain I-V extension.
- Add a recipe field only after the command sequence and safety behavior are
  confirmed.
- Add fake-SMU metadata support so dry-run artifacts can show the selected sense
  mode without pretending to change physics.
- Add unit tests for recipe validation, plan preview, metadata, and driver
  command generation.
- Add a hardware checklist covering terminal wiring, sense leads, open-sense
  behavior, output-off-on-error, and a known resistor validation.

## TODO - AC / Lock-In Measurement

Purpose: add SR860 or another lock-in as an optional secondary instrument.

Planned work:

- Introduce a secondary-instrument capability for reading lock-in channels
  without coupling it directly to the Keithley driver.
- Add lock-in recipe blocks under method-specific recipes, not as global fields.
- Store lock-in columns explicitly, for example `lockin_x_v`, `lockin_y_v`,
  `lockin_r_v`, `lockin_theta_deg`, plus timing metadata.
- Define synchronization policy: read lock-in after DC settle, read continuously,
  or read on external trigger.
- Add fake lock-in data generation for dry-run and plotting tests.
- Add lock-in-aware summaries and plots without breaking existing DC-only runs.

## TODO - Pulse Measurement

Purpose: support pulsed biasing only after DC safety and artifact flow are solid.

Planned work:

- Treat pulse as a separate method family rather than a flag on DC Drain I-V.
- Add pulse-specific safety limits: amplitude, width, period, duty cycle,
  maximum pulse count, and maximum energy/current where applicable.
- Define whether acquisition is point-by-point readback, buffered acquisition,
  oscilloscope-assisted, or lock-in-assisted.
- Add fake pulse traces before touching hardware.
- Require a dedicated hardware smoke-test recipe with conservative defaults.

## TODO - GUI And Recipe Builder

Purpose: keep GUI work on top of the same core API used by CLI.

Planned work:

- Build the PySide6 GUI as a client of recipe loading, plan preview, runners, and
  artifact readers.
- Make GUI recipe editing schema-driven so new method fields appear from recipe
  models instead of hand-written duplicate forms.
- Start with validated YAML editing and plan preview, then add structured form
  controls for common recipes.
- Keep live plotting and run review as artifact readers, not as separate data
  pipelines.

## Suggested Next Engineering Milestone

Before implementing another hardware method, add a small method registry and
review dispatch layer. The registry should map `measurement_type` to:

- recipe loader
- plan formatter
- runner entry point
- artifact summary/report/plot functions
- supported scheme step behavior

That will make future 4-probe, lock-in, pulse, and GUI work easier to add or
remove without turning the CLI or scheme runner into a large conditional block.
