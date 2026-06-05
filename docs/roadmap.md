# PyTransportMeasure Roadmap

This roadmap tracks the large development phases. Completed items are checked.

## Measurement Target

The long-term target is Hall-bar graphene transport measurement with dual-gate
scans. The measurement stack should grow in this order:

- two-terminal DC measurement with Keithley 2450
- four-terminal DC measurement with 2450 remote sense or separate voltage readout
- two-terminal AC measurement with Keithley bias plus SR860 lock-in readout
- four-terminal AC measurement with lock-in voltage/current geometry
- single-gate and dual-gate scans that compose the verified inner measurement
  methods

Current hardware on hand: two Keithley 2450 source meters and one SRS SR860
lock-in amplifier. SR860 command work must reference `SR860m.pdf` in the project
root.

## Completed

- [x] Phase 0: New package skeleton
  - `pyproject.toml`
  - `pytransport` package
  - `ptm` CLI entry point
  - pytest setup
- [x] Phase 1: Keithley 2450 Drain I-V hardware core
  - VISA resource listing
  - Keithley identify/probe
  - SCPI-mode Keithley 2450 voltage-source/current-measure path
  - 1 kOhm resistor smoke-test recipe
  - CSV points and JSON metadata
  - output-off on completion/error/interruption
- [x] Phase 2: Dry-run and safety foundation
  - fake SMU with Ohmic current model
  - software current safety checks
  - named safety presets
  - partial result saving
- [x] Phase 3: Recipe validation and plan preview
  - Pydantic YAML recipe schemas
  - `ptm validate`
  - `ptm plan`
  - `ptm preflight`
- [x] Phase 4: Drain I-V review artifacts
  - summaries
  - SVG plots
  - Markdown reports
  - fitted resistance
  - quality checks
- [x] Phase 5: Forward/backward and multi-segment Drain I-V
  - expanded sweep modes
  - plan preview for more complex sweep shapes
- [x] Phase 6: Batch sessions
  - batch YAML
  - repeat and interval support
  - batch reports, plots, CSV exports, points exports, stats
- [x] Phase 7: Measurement schemes
  - composed recipe/batch workflow
  - scheme-level summaries and artifacts
  - scheme overrides
  - parameter matrix expansion
- [x] Phase 8: Campaign analysis
  - campaign manifest
  - run filtering
  - grouped stats
  - histogram
  - portable campaign bundle
- [x] Phase 9: Single-gate dry-run foundation
  - two-SMU gate/drain recipe
  - coupled fake SMU support
  - single-gate summary, heatmap, stats, and report
- [x] Phase 10: Mixed measurement review
  - Drain I-V and single-gate runs coexist under `data/raw`
  - `inspect-run`, `list-runs`, campaign, and campaign bundle understand mixed
    measurement types
- [x] Phase 11: Single-gate scheme support
  - scheme steps can include `type: single_gate`
  - scheme review exports handle single-gate runs
- [x] Phase 12: Method extensibility planning
  - 4-probe deferred to TODO
  - AC, lock-in, pulse, and GUI extension policy documented
- [x] Phase 13: Project documentation pass
  - checklists
  - manual
  - roadmap
- [x] Phase 14: Method registry and dispatch cleanup
  - centralize saved-run summary, plot, report, campaign, scheme-review, and
    inspect dispatch
  - map each saved `measurement_type` to its review handlers
  - make future saved-run review support more localized
- [x] Phase 15: Extend method registry into planning dispatch
  - map recipe loaders and plan formatters
  - use registry-backed plan formatting in CLI and scheme plans
  - keep hardware-running dispatch explicit and conservative
- [x] Phase 16: Single-gate hardware smoke-test preparation
  - finalize two-Keithley wiring checklist
  - add conservative hardware recipe
  - verify output-off behavior for both drain and gate instruments
- [x] Phase 17: 4-probe / remote-sense design spike
  - confirm exact Keithley 2450 SCPI sequence from manual
  - decide whether remote sense is a capability config or method-specific config
  - define future dry-run metadata representation
  - add hardware smoke-test checklist before implementation

- [x] Phase 18: SR860 / lock-in foundation
  - add lock-in instrument interface
  - add fake lock-in
  - add optional secondary instrument recipe block
  - define timing/synchronization policy
- [x] Phase 19: AC measurement recipes
  - define AC method schema
  - add lock-in-aware point columns and artifacts
  - add dry-run examples and tests
- [x] Phase 20: Pulse measurement foundation
  - [x] start internal pulse recipe/runner/review module skeleton
  - [x] register pulse as a supported method type
  - [x] expose `ptm pulse-plan` and dry-run-only `ptm pulse`
  - [x] define pulse safety limits in a user-facing recipe
  - [x] define acquisition mode and saved CSV columns
  - [x] add fake pulse traces with tests
  - [x] add conservative dry-run recipe
  - [x] document pulse user workflow and hardware block policy
- [x] Phase 21a: Single-gate/two-SMU preflight gate
  - add `ptm single-gate-preflight`
  - probe drain and gate Keithley addresses before any two-SMU hardware run
  - block identical or missing drain/gate resources
  - expose single-gate preflight in GUI while keeping GUI hardware output
    conservative
- [x] Phase 22: SR860 probe and Keithley NPLC
  - read `SR860m.pdf` and document the exact SCPI command subset
  - add SR860 identify/probe/doctor path
  - add SR860 driver with read-only probe and X/Y/R/theta read primitives
  - add Keithley `nplc` recipe/config/driver/plan/report support
- [x] Phase 23a: AC lock-in two-instrument preflight
  - add `ptm ac-lockin-preflight`
  - check Keithley source and SR860 resources before AC hardware work
  - print AC preflight before blocked non-dry-run `ptm ac-lockin`
  - keep source output disabled because AC hardware acquisition is not active yet
- [x] Phase 23b: Two-terminal AC hardware smoke
  - add conservative `ac_lockin_hardware_smoke.yaml`
  - enable `ptm ac-lockin` hardware execution after preflight and confirmation
  - use Keithley source plus SR860 lock-in driver
  - write standard AC lock-in CSV, metadata, plot, and report artifacts
- [x] Phase 25a: Dual-gate dry-run foundation
  - add dual-gate recipe schema with drain, gate1, and gate2 instrument blocks
  - add dry-run runner over gate1 x gate2 x drain sweep points
  - add dual-gate CSV, metadata, heatmap, stats, report, and registry support
  - keep hardware execution blocked until topology and smoke tests are defined
- [x] Phase 25c: Dual-gate lock-in dry-run foundation
  - add two-Keithley gate-bias plus SR860 lock-in readout recipe schema
  - add dry-run runner over gate1 x gate2 lock-in readout points
  - add lock-in heatmap, stats, report, and registry support
  - keep hardware execution blocked until SR860 excitation/readout topology is smoke-tested
- [x] Phase 25d: SR860 expected-settings snapshot
  - add manual-backed SR860 settings fields to the shared lock-in recipe block
  - print expected reference/input/filter settings in AC and dual-gate lock-in plans
  - save expected settings in recipe snapshots and metadata without writing to SR860
  - keep hardware configuration as a separate future smoke-tested phase
- [x] Phase 25f: SR860 settings readback gate
  - query SR860 reference, excitation, input, range, sensitivity, time constant,
    filter slope, and sync filter settings in read-only probe/preflight paths
  - compare AC and dual-gate lock-in recipe expected settings against actual
    SR860 readback before hardware output is enabled
  - keep SR860 configuration write commands deferred to a later smoke-tested
    phase
- [x] Phase 23: PySide6 GUI foundation
  - optional `gui` dependency group
  - `ptm-gui` desktop entry point
  - method selection and recipe selection
  - plan preview using method registry
  - dry-run execution through shared core services
  - summary, metadata, report, recent run, and artifact-open views

## Next
- [ ] Phase 21b: Single-gate hardware smoke validation
  - confirm two Keithley addresses
  - verify drain/gate output-off behavior on real instruments
  - save first two-SMU smoke-test artifacts
- [x] Phase 24b: Terminal geometry abstraction
  - represent 2-terminal and 4-terminal geometry in recipes and metadata
  - add 2450 4-wire/remote-sense TODO implementation hook
  - keep SCPI selection explicit in plan/preflight before enabling output
- [x] Phase 25b: Dual-gate hardware topology design
  - decide DC three-source path vs AC source/readout plus two Keithley gates
  - define Hall-bar graphene dual-gate wiring and safety checklist
  - add preflight for the selected real hardware topology before enabling output
- [x] Phase 25e: Dual-gate lock-in hardware preflight
  - validate two gate Keithley addresses and one SR860 address
  - require distinct resources and successful read-only probes
  - print SR860 excitation/readout assumptions before output can be enabled
- [x] Phase 25g: Dual-gate lock-in readout smoke
  - add SR860 readout smoke command after three-instrument preflight
  - save lock-in X/Y/R/theta samples without enabling gate outputs
  - keep active dual-gate lock-in sweep disabled
- [x] Phase 25h: Dual-gate lock-in active-gate smoke
  - use the required topology block for SR860 excitation path and Hall-bar source-drain wiring
  - verify gate leakage and lock-in readout on a safe test device
  - apply one static gate-voltage pair, record leakage/readout, and always turn outputs off
- [x] Phase 25i: Dual-gate lock-in limited active sweep
  - require successful active-gate smoke first
  - enable a tiny bounded gate1 x gate2 scan with strict current limits
  - keep broad scans blocked until interruption/resume policy exists
- [x] Phase 25j: Dual-gate lock-in interruption and recovery policy
  - define whether interrupted active sweeps can resume or must restart
  - add operator-visible abort metadata and recovery checklist
  - keep broad scans blocked until this policy exists
- [x] Phase 25k: Dual-gate lock-in derived transport columns
  - derive nominal source-drain AC current from excitation amplitude and
    current-bias resistor
  - save lock-in resistance and conductance in point CSV, stats CSV, summaries,
    and reports
  - keep the derivation explicit as an analysis value rather than a hidden
    hardware-control behavior
- [x] Phase 25l: Dual-gate lock-in scan readiness gate
  - print total gate-grid point count, gate voltage steps, programmed settle
    time, default point guard status, and nominal AC current in plan/preflight
  - make broad recipes visibly fail the default hardware point guard before
    output can be enabled
  - keep the actual allowed broader scan size tied to lab feedback
- [x] Phase 25m: Dual-gate lock-in broader hardware threshold audit trail
  - require `--hardware-approval-note` when raising `--max-hardware-points`
    above the default guard
  - save default/requested guard, recipe point count, raised status, and
    approval note in run metadata
  - keep actual broad-scan size decision tied to lab feedback
- [x] Phase 25n: Lock-in read settling policy
  - add SR860 time-constant lookup and shared lock-in read-settle calculation
  - support `settle_time_constants` and explicit `read_settle_s` in lock-in
    recipes
  - apply the computed read settle before AC and dual-gate lock-in readout
  - print and save `lockin_time_constant_s` and `lockin_read_settle_s`
- [x] Phase 25o: SMU configuration snapshot
  - build Keithley source configs through a shared helper
  - save normalized compliance/range/terminal/NPLC snapshots in run metadata
  - cover Drain I-V, single-gate, dual-gate, AC lock-in, dual-gate lock-in,
    active-gate smoke, and pulse paths
- [x] Phase 25p: SMU configuration readback
  - add optional source-voltage config readback to the SMU interface
  - query Keithley source/sense function, terminal, NPLC, ranges, voltage
    readback, and accepted current-limit value after configure and before output
  - save best-effort `configured_*_smu_readback` metadata across runners
- [x] Phase 25q: SMU readback match gate
  - compare configured SMU intent against readback before enabling output
  - block readback-capable SMUs on mismatched NPLC, ranges, terminal, voltage
    readback, source/sense mode, or current limit
  - save `configured_*_smu_readback_check` in completed and partial metadata
- [x] Phase 25r: Output state metadata
  - track output-on/off attempts and errors per SMU role
  - save `output_state` metadata across active runners
  - keep legacy dual-gate lock-in `gate_outputs_enabled` and
    `outputs_off_after_run` fields synchronized
- [x] Phase 25s: Zero before output off
  - attempt `set_voltage(0.0)` before output off for every active SMU role
  - save `zero_before_off_*` metadata in `output_state`
  - make fake dry-run cleanup mirror hardware cleanup intent
- [x] Phase 25t: Voltage command tracking
  - route runner voltage commands through the output-state helper
  - save command count, last commanded voltage, command error, and
    pre-cleanup setpoint per SMU role
  - use this for partial-run review before broader Hall-bar scans
- [x] Phase 25u: Dual-gate lock-in acceptance audit
  - add `ptm dual-gate-lockin-audit` for saved limited active sweeps
  - check completed status, point completeness, SMU readback, NPLC declaration,
    output cleanup, zero-before-off, and SR860 setting readback
  - write `dual_gate_lockin_acceptance.md` as the artifact checkpoint before
    expanding hardware scans
- [x] Phase 25v: Explicit Keithley NPLC hardware gate
  - require explicit NPLC before CLI paths enable Keithley hardware output
  - keep dry-run and read-only SR860 smoke paths available without NPLC
  - centralize the policy in a measurement-parameter guard for future methods
- [x] Phase 25w: Keithley source-delay config
  - add optional `source_delay_s` to Keithley instrument blocks
  - send/read back `SOUR:VOLT:DEL` through the shared SMU config path
  - save and compare source delay in `configured_*_smu` metadata/readback
- [x] Phase 25x: Active geometry capability guard
  - initially blocked active runners unless `measurement_geometry.method` was
    `two_terminal`
  - keep terminal-count guard as a separate safety trigger
  - preserve 4-probe/four-terminal as an explicit future method capability
- [x] Phase 25y: Accepted previous run guard for broader dual-gate scans
  - require `--accepted-previous-run` when raising `--max-hardware-points`
  - run strict `dual-gate-lockin-audit` on the previous artifact before output
  - save accepted previous run path, audit pass state, and point counts in
    `hardware_guard`
- [x] Phase 25z: Explicit Keithley range hardware gate
  - require `voltage_range_v`, `current_range_a`, and `nplc` before active
    Keithley hardware output paths can start
  - keep dry-run paths available for recipe/artifact tests with incomplete SMU
    settings
  - add the missing guard to dual-gate lock-in active-gate smoke
- [x] Phase 25aa: Dual-gate lock-in grid identity metadata
  - save the ordered gate1 x gate2 planned grid in run metadata
  - save a stable SHA-256 grid signature for artifact comparison
  - audit that `points.csv` follows the saved grid when metadata is available
- [x] Phase 25ab: Dual-gate lock-in scale-up compatibility guard
  - compare accepted previous run metadata against the candidate recipe before
    raised-point hardware output
  - require compatible geometry, topology, lock-in settings, gate SMU settings,
    compliance policy, and grid subset
  - save scale-up compatibility state in `hardware_guard`
- [x] Phase 25ac: Dual-gate lock-in scale-up pre-check CLI
  - add `ptm dual-gate-lockin-scale-up-check`
  - run strict acceptance and scale-up compatibility checks without hardware
    output
  - use this as the final dry gate before a raised-point hardware run
- [x] Phase 25ad: Accepted-run scale-up recipe template
  - add `ptm dual-gate-lockin-scale-up-template`
  - copy accepted run topology, SR860 settings, Keithley settings, compliance,
    and metadata structure into a candidate recipe
  - change only the requested gate grid and immediately run scale-up pre-check
- [x] Phase 25ae: Dual-gate lock-in leakage margin audit
  - compute gate1/gate2 leakage maxima from accepted `points.csv`
  - report leakage/compliance margin in `dual-gate-lockin-audit`
  - warn when margin is below 10x even if the run otherwise passes
- [x] Phase 25af: Block scale-up on leakage-margin warnings
  - keep leakage-margin warnings visible in the acceptance audit
  - block raised-point hardware runs when the accepted previous run has
    scale-up-blocking leakage warnings
  - make `dual-gate-lockin-scale-up-check` fail before hardware when the
    previous limited run needs leakage-margin review
- [x] Phase 25ag: Guarded four-terminal lock-in geometry
  - allow `four_terminal` lock-in recipes only when SR860 uses voltage input
    and differential `a-b` input
  - require dual-gate Hall-bar voltage contacts to be separate from excitation
    contacts before runner execution
  - add AC lock-in and dual-gate lock-in four-terminal dry-run recipes
- [x] Phase 25ah: Lock-in measurement-context reporting
  - add shared geometry/contact context formatting for lock-in artifacts
  - include lock-in input mode and voltage input in AC lock-in reports
  - include Hall-bar voltage contacts and excitation contacts in dual-gate
    lock-in summary and report artifacts
- [x] Phase 25ai: Hall-bar sheet transport derivation
  - add voltage probe role and optional channel length/width to dual-gate
    lock-in topology
  - derive sheet resistance/conductivity for longitudinal Vxx measurements
  - save sheet transport columns in points CSV, stats CSV, summary, and report
- [x] Phase 25aj: Hall-voltage transport derivation
  - add optional magnetic field to dual-gate lock-in topology
  - derive Hall resistance for Vxy probes
  - estimate fixed-field 2D carrier density when `magnetic_field_t` is declared
- [x] Phase 25ak: Keithley measurement parameter audit
  - keep Keithley `nplc` explicit in the shared SMU config path
  - document NPLC as current integration time in power-line cycles
  - centralize required Keithley hardware parameter labels and reasons
- [x] Phase 25al: Runtime SR860 settings gate
  - reuse the shared SR860 setting comparison path outside preflight
  - save active-run SR860 setting readback checks in metadata
  - block gate output when runtime SR860 readback contradicts the recipe
- [x] Phase 25am: Scale-up review packet
  - have `dual-gate-lockin-scale-up-template` write a companion review markdown
  - include scale-up check, preflight, hardware command template, and full plan
  - keep actual broader hardware execution tied to lab feedback
- [x] Phase 25an: AC lock-in runtime SR860 gate
  - save runtime SR860 setting readback checks in AC lock-in metadata
  - block Keithley source output when SR860 readback contradicts the recipe
  - keep fake-lock-in dry-runs available when readback is unavailable
- [x] Phase 25ao: Hall antisymmetrization analysis
  - add `ptm dual-gate-lockin-hall-antisym` for paired `+B`/`-B` Hall runs
  - write antisymmetrized Hall resistance, field-even component, and density CSV
  - require completed Hall runs with equal-magnitude opposite magnetic fields
- [x] Phase 25ap: Hall mobility extraction analysis
  - add `ptm dual-gate-lockin-hall-mobility`
  - combine antisymmetrized Hall density with longitudinal sheet conductivity
  - write signed and magnitude mobility in SI and cm^2/V/s lab units
- [x] Phase 25aq: Hall zero-field offset correction analysis
  - add `ptm dual-gate-lockin-hall-zero-correct`
  - subtract matched `B=0` Hall resistance from finite-field Hall resistance
  - write corrected Hall resistance and carrier density artifacts
- [x] Phase 25ar: Mobility source generalization
  - allow `ptm dual-gate-lockin-hall-mobility` to accept either
    `hall_antisym.csv` or `hall_zero_corrected.csv`
  - preserve source kind and source resistance columns in mobility artifacts
  - keep the same longitudinal Vxx sheet-conductivity input contract
- [x] Phase 25as: Hall-bar recipe suite template
  - add `ptm dual-gate-lockin-hall-suite-template`
  - generate Vxx, `+B` Vxy, `-B` Vxy, and optional `0B` Vxy recipes from one
    base dual-gate lock-in recipe
  - write a review markdown with plan, preflight, guarded hardware, and analysis
    command templates
- [x] Phase 25at: Hall-bar recipe suite consistency check
  - add `ptm dual-gate-lockin-hall-suite-check`
  - verify shared gate sweeps, SMU/SR860 settings, safety preset, topology, and
    point counts across generated Vxx/Vxy recipes
  - verify Vxx/Hall roles and `+B`/`-B`/`0B` magnetic-field metadata before
    hardware use
- [x] Phase 25au: Hall-bar suite aggregate plan
  - add `ptm dual-gate-lockin-hall-suite-plan`
  - print one hardware-free Vxx/+B/-B/0B runbook with measurement order,
    preflight commands, guarded hardware templates, and Hall analysis commands
  - stop with a nonzero exit code when the suite consistency check fails
- [x] Phase 25av: Dual-gate lock-in resume-from-partial-run
  - add `ptm dual-gate-lockin --resume-from-run <partial_run_dir>`
  - create a new run directory, copy the partial `points.csv` prefix, and
    continue from the next unmeasured grid point
  - require the resume source grid signature to match the current recipe
- [x] Phase 25aw: Dual-gate lock-in resume precheck
  - add `ptm dual-gate-lockin-resume-check`
  - verify partial-run compatibility without VISA or hardware output
  - print the next gate-grid index and gate voltages before resume
- [x] Phase 25ax: Dual-gate lock-in checkpoint stop
  - add `ptm dual-gate-lockin --stop-after-new-points <N>`
  - stop cleanly with `abort_class: checkpoint` after a bounded number of new
    points
  - let hardware point guard evaluate the bounded invocation size
- [x] Phase 25ay: Dual-gate lock-in chunk plan
  - add `ptm dual-gate-lockin-chunk-plan`
  - split a planned gate grid into bounded checkpoint chunks
  - print resume-check and hardware command sequence templates for each chunk
- [x] Phase 25az: Dual-gate lock-in chunk stitching
  - add `ptm dual-gate-lockin-stitch-chunks`
  - merge newly measured rows from checkpoint chunk runs into one standard
    dual-gate lock-in run artifact
  - support stats, plot, report, and run-index artifacts on the stitched run
- [x] Phase 25ba: Hall-suite chunk workflow plan
  - add `ptm dual-gate-lockin-hall-suite-chunk-plan`
  - combine suite consistency, per-recipe chunk acquisition, stitching, and
    stitched-run Hall analysis commands in one hardware-free runbook
- [x] Phase 25bb: Dual-gate lock-in first broader hardware scan packet
  - add `ptm dual-gate-lockin-broader-scan-packet`
  - summarize accepted-run audit, scale-up compatibility, measurement
    parameters, chunked acquisition commands, stitch commands, and strict audit
    in one lab execution packet
  - make NPLC/range/compliance visible before the broader scan starts
- [x] Phase 25bc: Dual-gate lock-in checkpoint chunk acceptance
  - add `ptm dual-gate-lockin-chunk-audit`
  - accept clean checkpoint runs without requiring full-run completion
  - still require measured-prefix grid consistency, SMU readback, output
    cleanup, leakage margin, and SR860 setting readback before resuming
- [x] Phase 25bd: Dual-gate lock-in chunk feedback summary
  - add `ptm dual-gate-lockin-chunk-feedback`
  - summarize several checkpoint chunk audits into one continue/review report
  - report worst leakage and minimum leakage/compliance margins before deciding
    whether to keep chunk size, NPLC, settle time, and SR860 sensitivity
- [x] Phase 25be: First lab-feedback recipe adjustment
  - add `ptm dual-gate-lockin-adjust-recipe`
  - create adjusted recipes that keep the gate grid/topology while changing
    NPLC, gate settle time, SR860 sensitivity/time constant, and read-settle
    parameters after lab feedback
  - write an adjustment review markdown with plan/preflight commands
- [x] Phase 25bf: Hall-suite full acquisition readiness
  - add `ptm dual-gate-lockin-hall-suite-adjust-recipes`
  - generate adjusted Vxx/+B/-B/0B recipe sets as a group after chunk feedback
  - keep shared Keithley NPLC, gate settle, and SR860 settings consistent before
    suite preflight and chunked acquisition
- [x] Phase 25bg: Hall-suite acquisition package
  - add `ptm dual-gate-lockin-hall-suite-package`
  - produce one folder-level packet for adjusted suite recipes, chunk feedback,
    preflight outputs, acquisition notes, and analysis commands
  - make the lab-laptop handoff explicit for no-local-hardware development
  - keep the package hardware-free until the researcher runs it in the lab
- [x] Phase 25bh: Hall-suite execution result intake
  - add `ptm dual-gate-lockin-hall-suite-intake`
  - inspect a completed package session from the lab laptop
  - verify Vxx/+B/-B/0B run folders against the packaged recipes and manifest
  - produce a one-command post-run audit before Hall analysis
- [x] Phase 25bi: Hall-suite analysis orchestration
  - add `ptm dual-gate-lockin-hall-suite-analyze`
  - run accepted suite outputs through antisymmetry, optional zero-field
    correction, and mobility analysis from one command
  - require result intake PASS before writing derived Hall artifacts
  - keep analysis provenance tied to package manifest and run folders
- [x] Phase 25bj: Hall-suite analysis review
  - summarize density, sheet conductivity, and mobility maps from the
    orchestrated analysis folder
  - flag sign changes, missing gate points, and suspicious zero-field offsets
  - write one review report for deciding the next graphene gate scan
- [x] Phase 25bk: Hall-suite next-scan proposal
  - use accepted analysis review artifacts to propose the next gate window and
    spacing for graphene Hall-bar scans
  - keep lab approval mandatory before writing any hardware recipe
  - preserve Keithley NPLC/range/compliance and SR860 settings unless the
    proposal explicitly calls out why they should change
- [x] Phase 25bl: Approved next-scan recipe generation
  - turn an approved next-scan proposal into adjusted Hall-suite recipes
  - require an approval note before writing hardware recipes
  - keep NPLC/range/compliance/SR860 settings unchanged by default and record
    any deliberate measurement-setting changes
- [x] Phase 25bm: Approved next-scan acquisition package
  - package the approved next-scan recipe suite with the proposal and approval
    review artifacts
  - include a hardware runbook that highlights changed gate grid and preserved
    NPLC/range/compliance/SR860 settings
  - keep chunked acquisition and post-run intake as the default hardware path
- [x] Phase 25bn: Approved next-scan dry-run package rehearsal
  - run the approved next-scan package through fake acquisition, intake,
    analysis, review, and proposal in one verification workflow
  - verify package provenance survives the full loop
  - keep the rehearsal hardware-free for local development
- [x] Phase 25bo: Hall workflow command consolidation
  - add one read-only workflow status command for Hall-suite packages
  - summarize which stages exist: package, rehearsal, intake, analysis, review,
    proposal, approval, approved package
  - keep hardware execution separate from status/reporting commands
- [x] Phase 25bp: Hall workflow module split
  - move Hall workflow orchestration helpers out of the CLI into a dedicated
    module
  - keep CLI commands thin wrappers around core APIs
  - preserve existing command behavior and tests
- [x] Phase 25bq: CLI Keithley parameter guard
  - add direct CLI regression coverage for Drain I-V hardware parameter gates
  - verify missing NPLC/ranges block `ptm run` before preflight or output setup
  - keep dry-run usable for recipe and artifact validation without hardware
- [x] Phase 25br: Hall workflow module tests
  - add direct unit tests for the reusable Hall workflow module APIs
  - keep CLI tests focused on argument wiring and exit codes
  - verify status and rehearsal helpers without relying only on CLI end-to-end
    coverage
- [x] Phase 25bs: Measurement parameter audit expansion
  - add reusable audit output for all active Keithley source blocks
  - surface NPLC/range/compliance/terminal/source-delay consistency in one
    machine-readable artifact
  - prepare the audit for two-SMU gate plus SR860 Hall-bar workflows
- [x] Phase 25bt: Hall package Keithley audit integration
  - write Keithley parameter audit JSON/Markdown into Hall-suite acquisition
    packages
  - include per-recipe PASS/MISSING status in the Hall workflow status summary
  - make lab handoff packages carry measurement-parameter audit provenance
- [x] Phase 25bu: Hall package SR860 audit integration
  - write declared SR860 setting summaries into Hall-suite acquisition packages
  - expose SR860 setting audit status in workflow handoff summaries
  - keep Keithley and lock-in measurement-condition provenance side by side
- [x] Phase 25bv: Hall package manifest schema cleanup
  - normalize Hall package audit manifest records for Keithley and SR860
  - add direct tests for manifest backward compatibility
  - document package manifest fields for external lab notebooks and scripts
- [x] Phase 25bw: Keithley NPLC recipe range guard
  - validate Keithley current-measurement NPLC at recipe load time
  - expose the supported NPLC range in hardware parameter audit messages
  - document NPLC as a deliberate measurement condition for Hall scans
- [x] Phase 25bx: Hall package manifest validator
  - add a dedicated command to validate package manifest schema and artifact
    paths without running the full workflow status report
  - report missing package files, audit files, and schema incompatibilities in
    machine-readable JSON
  - prepare the validator for GUI package inspection
- [x] Phase 25by: Hall-suite lab handoff smoke bundle
  - produce a compact pre-lab smoke checklist from a validated package
  - include exact identify/probe/preflight commands for two Keithleys and SR860
  - keep the generated handoff artifact hardware-free and package-local
- [x] Phase 25bz: Hall package hardware command gating review
  - audit generated active hardware commands for explicit approval notes and
    bounded point counts
  - make package handoff checks fail if guarded command templates lose the
    hardware-output safety flags
  - keep the review hardware-free and reusable by GUI package inspection
- [x] Phase 25ca: Hall package handoff summary index
  - combine package validation, lab smoke checklist, and hardware command review
    outputs into one package-local handoff summary
  - expose a single PASS/REVIEW state for lab notebook attachment
  - keep individual JSON artifacts as the detailed audit trail
- [x] Phase 25cb: Hall package lab-return manifest
  - create a package-local manifest for files returned from the lab laptop after
    acquisition
  - record run folders, operator notes, package hash, and post-run intake status
  - keep the handoff and return records connected for later analysis
- [x] Phase 25cc: Hall package lifecycle status
  - combine handoff summary, lab-return manifest, intake, analysis, review, and
    next-scan proposal into a single lifecycle status report
  - expose which package stage is ready, missing, or requires review
  - prepare package lifecycle state for GUI package inspection
- [x] Phase 25cd: Hall package measurement-condition lifecycle gate
  - surface Keithley NPLC/range/compliance and SR860 setting audit state in the
    lifecycle report
  - make lifecycle handoff/analysis states explicitly depend on preserved
    measurement-condition artifacts
  - keep Hall-bar package transitions focused on reproducible measurement
    conditions, not only file existence
- [x] Phase 25ce: Hall package acquisition-condition drift guard
  - compare package audit records against returned run metadata before analysis
  - flag changed Keithley NPLC/range/compliance/source-delay or SR860 settings
    as measurement-condition drift
  - keep repeated Hall scans comparable across lab-laptop runs
- [x] Phase 25cf: Hall condition drift summary in lifecycle status
  - surface acquisition-condition drift PASS/FAIL in lifecycle status after
    result intake
  - make package lifecycle visibly block analysis and next-scan decisions when
    returned metadata drifts from packaged measurement conditions
- [x] Phase 25cg: Hall run metadata condition snapshot report
  - write a compact per-run measurement-condition table from returned metadata
  - compare Vxx/+B/-B/0B Keithley and SR860 settings side by side
  - make lab-notebook review easier before deeper Hall analysis
- [x] Phase 25ch: Hall condition snapshot lifecycle integration
  - surface condition snapshot existence in lifecycle status
  - make lab handoff/return artifacts point to snapshot, drift, and intake
    reports together
- [x] Phase 25ci: Hall return bundle index
  - write a package-local index that links intake, condition snapshot, drift,
    lab-return manifest, lifecycle status, and analysis artifacts
  - give lab notebook entries one compact return artifact table
- [x] Phase 25cj: Hall return bundle index lifecycle integration
  - surface return bundle index existence in lifecycle status
  - let package lifecycle mark post-analysis return bundles as archived for lab
    notebook handoff
- [x] Phase 25ck: Hall measurement-mode execution matrix
  - define the next measurement-focused implementation matrix for two-terminal
    DC, four-terminal DC, two-terminal AC, four-terminal AC, and Hall-suite
    dual-gate runs
  - keep convenience/UI work secondary to hardware-facing measurement paths
- [x] Phase 25cl: Four-terminal DC design gate
  - inspect Keithley 2450 remote-sense / 4-wire SCPI path before enabling any
    four-terminal DC output
  - design recipe schema, contact topology guard, preflight, and dry-run runner
    for DC four-probe measurement
- [x] Phase 25cm: Four-terminal DC recipe schema draft
  - add a non-executing recipe model for Keithley 2450 remote-sense Drain I-V
    with explicit force/sense contacts and `dc_sense_mode`
  - keep hardware execution blocked until driver SCPI tests and preflight
    readback are implemented
- [x] Phase 25cn: Four-terminal DC Keithley driver SCPI tests
  - add a driver-level remote-sense configuration primitive for current
    measurement without wiring it into active runners
  - verify exact `:SENS:CURR:RSEN ON/OFF` command and readback behavior with
    fake VISA before any hardware run exists
- [x] Phase 25co: Four-terminal DC preflight readback gate
  - add non-output preflight readback planning for `:SENS:CURR:RSEN?`
  - keep remote-sense output blocked until preflight proves terminal, range,
    NPLC, compliance, and remote-sense readback checks are available
- [x] Phase 25cp: Four-terminal DC fake metadata runner skeleton
  - add a dry-run/fake artifact path for four-terminal DC metadata and reports
  - keep real Keithley remote-sense output blocked until lab preflight feedback
    confirms the readback gate
- [x] Phase 25cq: Four-terminal DC active-run command review
  - design the exact guarded remote-sense output sequence using preflight
    evidence and Keithley 2450 SCPI behavior
  - require explicit approval gates before wiring `:SENS:CURR:RSEN ON` into
    any active runner
- [x] Phase 25cr: Four-terminal DC guarded active runner draft
  - implement the remote-sense active runner behind explicit lab approval gates
  - require passing command-review evidence before any output can be enabled
- [x] Phase 25cs: Four-terminal DC lab smoke result intake
  - ingest the first guarded active runner metadata from the lab laptop
  - audit remote-sense readback, output cleanup, NPLC/range/compliance, and
    fitted resistance before broadening the method
- [ ] Phase 25ct: Four-terminal DC lab feedback hardening
  - use the first real lab-laptop intake report to tighten Keithley 2450
    remote-sense cleanup/readback assumptions
  - decide whether the next smoke should broaden point count, add contact
    fixture metadata, or pause for driver correction
  - keep NPLC/range/compliance changes explicit and reviewable before any
    device measurement
- [x] Phase 24: GUI recipe builder foundation
  - YAML recipe editor
  - schema validation using existing Pydantic recipe models
  - validated save-as workflow
  - prevent GUI-only measurement logic
- [x] Phase 24c: GUI run browser
  - load indexed runs
  - inspect saved run summary/metadata/report
  - open saved run folder, plot, and report
  - tolerate UTF-8 BOMs in `data/run_index.jsonl`
- [x] Phase 24d: GUI plot preview
  - choose primary plot artifact from saved metadata
  - render SVG plots in-app
  - keep external artifact opening available
- [x] Phase 24e: GUI Drain I-V form builder
  - edit common Drain I-V fields in a structured form
  - convert form values into validated YAML
  - keep advanced recipes editable through YAML
- [x] Phase 24f: GUI editor-backed runs
  - plan from current YAML editor text
  - dry-run from current YAML editor text
  - keep recipe path as load/save source
- [x] Phase 24g: GUI Drain I-V preflight
  - preflight from current YAML editor text
  - show VISA resources and Keithley probe report
  - keep GUI hardware output controls unavailable
- [x] Phase 24h: GUI guarded Drain I-V hardware run
  - explicit confirmation before output can be enabled
  - rerun preflight inside the hardware worker
  - reuse core Drain I-V runner and artifact pipeline
- [x] Phase 24i: lab feedback bundle
  - package one run folder with inspection, quality, environment, and manifest
  - expose `ptm feedback-bundle`
  - expose GUI `Feedback Bundle`
- [x] Phase 24j: lab laptop doctor
  - report Python/platform/PyVISA environment
  - list VISA resources
  - optionally check and probe a Keithley address
- [x] Phase 24k: GUI lab doctor
  - run doctor from GUI
  - infer Drain I-V address from current editor YAML
  - display diagnostics in a Doctor tab
- [x] Phase 24l: GUI progress stream
  - stream dry-run point progress to GUI
  - stream guarded Drain I-V hardware point progress to GUI
  - reuse core runner progress callbacks
- [x] Phase 24m: GUI session log
  - persist GUI Doctor/Preflight/Progress/error events to `data/gui_logs`
  - show the current session log in the GUI
  - include the GUI session log in feedback bundles
  - allow CLI feedback bundles to include extra diagnostic files
- [x] Phase 24n: GUI usability pass
  - collapse dry-run settings by default
  - reduce unnecessary GUI minimum-size pressure
  - preserve Session Log scroll position unless the user is already at the bottom
- [x] Phase 24o: GUI workspace reorganization and live plot
  - split GUI into Measurement, Instruments, and Analysis workspaces
  - move Doctor and instrument status into Instruments
  - move saved-run loading, plot/report review, and feedback bundles into Analysis
  - replace stretched SVG preview with a points-based Qt plot
  - add live Drain I-V point plotting during dry-run and guarded hardware run
- [x] Phase 24p: GUI instrument refresh and communication test
  - refresh VISA resources from the Instruments workspace
  - populate a selectable resource/address field
  - test communication with the selected address
  - clarify recipe tool button names and directions
- [x] Phase 24q: GUI recipe sync status
  - show that Recipe YAML is the execution source
  - warn when form edits have not yet been applied back to YAML
  - warn when YAML edits may need YAML -> Form sync
- [x] Phase 24r: GUI workflow guide
  - track Check YAML, instrument refresh/test, Plan, Dry Run, Preflight, and
    Hardware Run state
  - show the next safe GUI action from one workflow tab
- [x] Phase 24s: GUI dry-run model scroll
  - keep the collapsible dry-run model readable after expansion
  - use a scroll container for fake-model settings in constrained windows
- [x] Phase 24t: GUI cooperative stop
  - add a Stop Run button for active GUI dry-runs and guarded hardware runs
  - stop Drain I-V at safe runner checkpoints with partial artifacts and output
    off cleanup
- [x] Phase 24u: lab context metadata
  - add cooldown/contact/notebook fields to recipe experiment metadata
  - expose lab context in GUI Drain I-V form, validation, reports, and run index
- [x] Phase 24v: GUI run filters
  - filter Analysis runs by sample, device, cooldown, tag, method, and status
  - show lab context fields in the GUI run table
- [x] Phase 24w: GUI Analysis source folder, sorting, and loaded row
  - scan selected run folders or parent folders in Analysis
  - enable Runs table sorting and highlight the currently loaded run
- [x] Phase 24x: GUI Recipe Overview
  - summarize the current YAML by method, experiment, instrument, sweep, pulse,
    lock-in, output, and checks blocks
  - update the overview from the editor YAML without adding GUI-only recipe
    parsing
  - keep the path open for schema-driven form builder work
- [x] Phase 24y: GUI schema recipe builder MVP
  - generate `Recipe Form` fields from validated Pydantic recipe models
  - support Drain I-V, single-gate, AC lock-in, and pulse recipe editing through
    one form path
  - apply form values back to YAML through the method recipe model
  - keep advanced YAML editing available for complex fields
- [x] Phase 24z: GUI scheme builder MVP
  - compose multiple recipes and method steps from the GUI
  - validate and preview scheme plans using the shared scheme core
  - keep generated scheme YAML visible and editable
- [x] Phase 24aa: GUI Scheme Drain I-V overrides
  - expose per-step Drain I-V measurement suffix and sweep overrides
  - reuse one base recipe for multiple scheme conditions
  - round-trip override YAML through the Schemes table

## Next GUI

- [x] Phase 24ab: GUI scheme dry-run and saved scheme review draft
  - run scheme dry-runs from the GUI
  - show saved scheme summary/report/artifacts in the Schemes workspace
  - export scheme report, runs CSV, points CSV, stats CSV, and overlay SVG
  - keep hardware scheme execution gated behind later smoke tests
- [x] Phase 24ac: GUI saved scheme browser
  - load existing scheme summaries from `data/schemes`
  - inspect older scheme reports and artifacts from the GUI
  - compare saved scheme runs without rebuilding the scheme YAML
- [x] Phase 24ad: GUI scheme comparison view
  - compare selected saved schemes side by side
  - surface per-step run statistics without opening CSV files
  - reuse scheme review stats so GUI and CLI values match
- [x] Phase 24ae: GUI scheme overlay preview
  - add scheme overlay preview without SVG distortion
  - redraw saved `points.csv` data on the GUI canvas
  - keep report SVG export as a separate artifact path
- [x] Phase 24af: GUI scheme comparison export
  - export the GUI comparison table as CSV
  - add optional saved scheme filters
- [x] Phase 24ag: GUI saved scheme table polish
  - persist last selected scheme source folder
  - improve saved table column sizing and filter ergonomics
- [ ] Phase 24ah: GUI saved source persistence expansion
  - remember more non-hardware GUI preferences only when useful
  - keep persisted state separate from recipes and measurement metadata
- [ ] Phase 25: GUI hardware-run controls
  - guarded preflight view
  - explicit confirmation
  - output-off/error display
  - live progress streaming

## Long-Term Direction

- [ ] Method plugins or modules for additional instruments and measurement
  families.
- [ ] More robust live monitoring beyond Drain I-V cooperative stop.
- [x] Richer metadata for sample, device, cooldown, contacts, and lab notebook
  references.
- [ ] Automated report templates for publications and internal experiment logs.
- [ ] Hardware integration tests that can be run explicitly in the lab.
