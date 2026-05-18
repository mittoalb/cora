# Affordances

*Closed-enum primitives a [Family](../catalog/families.md) declares it supports. Set-membership over Affordances drives the cross-BC Plan-bind matching engine: `union(wired_asset.families.affordances) ⊇ method.capability.required_affordances`.*

An **Affordance** is a claim about what a device can do. Affordances are declared on Families (Equipment BC). The contract a Method must satisfy is declared one layer up on its bound **Capability** template (Recipe BC `Capability.required_affordances`). At `define_plan` time, the union of every wired Asset's Families' affordances must cover the bound Method's Capability's required set — otherwise the handler raises `PlanAffordancesNotSatisfiedError` (409).

## Three patterns

The v1 closed enum carries 28 items in three explicit patterns. The split is deliberate (see `project_capability_research` section 5a in user-memory):

- **Pattern A — Action affordances (`-able` / `-ible` suffix)**: "device supports doing X". 24 items. Reads as a predicate: a `RotaryStage` Family is `Rotatable`, a Camera Family is `Imageable`.
- **Pattern B — Signal affordances (noun)**: "device exposes signal X". 3 items. Names a data-flow shape rather than an action.
- **Pattern C — Lifecycle affordances (noun)**: "device has lifecycle property X". 1 item. For passive parts whose identity is operationally tracked even though they have no command surface.

This convention is grounded in [Swift API Design Guidelines](https://www.swift.org/documentation/api-design-guidelines/) ("Protocols that describe a _capability_ should be named using the suffixes `able`, `ible`, or `ing`"), [.NET Framework Design Guidelines](https://learn.microsoft.com/en-us/dotnet/standard/design-guidelines/names-of-classes-structs-and-interfaces) ("DO name interfaces with adjective phrases"), and [W3C SOSA](https://www.w3.org/TR/vocab-ssn/) `ObservableProperty` / `ActuatableProperty`.

## Pattern A — Action affordances (24)

### Motion (8)

| Affordance | Contract |
|---|---|
| `Rotatable` | Device supports a rotational degree of freedom with a set position command. |
| `Translatable` | Device supports a linear (single-axis) degree of freedom with a set position command. |
| `Homeable` | Device supports a `home` operation that drives to a reference position and zeros the encoder. |
| `Limitable` | Device honors operator-configured software-limit min/max bounds, refusing motion past them. |
| `PositionTriggerable` | Device emits a hardware trigger pulse when its encoder crosses configured positions (PandA `PCOMP`). |
| `PositionCapturable` | Device latches encoder values into a buffer on external trigger edges (PandA `PCAP`; DAQ-side mirror of `PositionTriggerable`). |
| `Posable` | Device accepts a coordinated multi-DOF pose command (typically 6-DOF X/Y/Z/U/V/W) referred to a configurable pivot/tool/work frame; for hexapods + parallel kinematics. |
| `Indexable` | Device has a finite enumerated set of mutually-exclusive named positions with a `go to named position` operation (filter wheel, mirror coating stripe, monochromator crystal pair). |

### Imaging (2)

| Affordance | Contract |
|---|---|
| `Imageable` | Device acquires 2D image frames on exposure/trigger; supports basic capture. |
| `Binnable` | Device supports on-sensor pixel binning (N×N combining) to trade resolution for SNR/speed. |

### Triggering and timing (3)

| Affordance | Contract |
|---|---|
| `Triggerable` | Device accepts an external edge trigger to start a single timed operation (exposure, sample, etc.). |
| `Gateable` | Device integrates over the duration of an external level signal (gate high = active, gate low = idle). |
| `Synchronizable` | Device aligns its internal clock to an external master clock or sync signal. |

### Streaming and data (4)

| Affordance | Contract |
|---|---|
| `Streamable` | Device pushes data continuously over a transport without per-frame request/response handshake. |
| `PreTriggerBufferable` | Device holds an internal ring buffer with a configurable pre/post-trigger split; on trigger, the past N frames are preserved. |
| `Compressible` | Device applies a lossless or lossy codec to outgoing data (JPEG, LZ4, etc.) at runtime. |
| `FileWritable` | Device writes acquired data to a file path the operator configures (HDF5, TIFF, ADF, etc.). |

### Optics and environment (5)

| Affordance | Contract |
|---|---|
| `Coolable` | Device exposes a setpoint for its thermal control loop (sensor cooling, hexapod thermal management, etc.). |
| `PIDControllable` | Device's control loop exposes P/I/D gains for operator tuning. |
| `Shutterable` | Device has an open/close shutter that the operator can command. |
| `Attenuable` | Device reduces the intensity of an incident beam by an operator-set factor (typically via discrete filters). |
| `Bendable` | Device's optical surface (mirror) has actively-driven curvature/figure (mechanical bender, bimorph piezo array, thermal); see [NXmirror](https://manual.nexusformat.org/classes/base_classes/NXmirror.html) `bend_angle_x/y`. |

### Reporting (2)

| Affordance | Contract |
|---|---|
| `Identifiable` | Device returns a persistent identifier (serial number, MAC, etc.) on query. |
| `Reportable` | Device returns a health/status reading on query (temperature, error count, firmware version, etc.). |

## Pattern B — Signal affordances (3)

| Affordance | Contract |
|---|---|
| `EncoderInput` | Device accepts an external encoder signal as its position feedback source. |
| `EncoderOutput` | Device emits its position as an encoder signal that downstream devices can read. |
| `PulseGenerator` | Device generates configurable digital pulse trains (width, period, count) for downstream timing. |

## Pattern C — Lifecycle affordances (1)

| Affordance | Contract |
|---|---|
| `Consumable` | Device is a passive part whose identity, material, thickness, lot, and install/remove history are operationally tracked, even though it has no command surface (scintillator screens, filters, sample holders, target foils). |

## Cross-vocabulary mapping

Affordance ⇄ adjacent-vocabulary cross-walk for adapter authors:

| Affordance | ros2_control | W3C WoT TD | NeXus | OPC UA LADS | PandABox | EPICS |
|---|---|---|---|---|---|---|
| `Rotatable` | `HW_IF_POSITION` (axis=rotary, dir=command) | `PropertyAffordance` (writable) | `NXpositioner` | `AnalogControlFunction` | — | `motorRecord` |
| `Translatable` | `HW_IF_POSITION` (axis=linear, dir=command) | `PropertyAffordance` (writable) | `NXpositioner` | `AnalogControlFunction` | — | `motorRecord` |
| `Homeable` | `HW_IF_HOME` (action) | `ActionAffordance` | — | `MoveControlFunction` | — | `motorRecord HOMR/HOMF` |
| `PositionTriggerable` | — | — | — | — | `PCOMP` | — |
| `PositionCapturable` | — | — | — | — | `PCAP` | — |
| `Triggerable` | — | `ActionAffordance` | `NXdetector.acquisition_mode=triggered` | — | `PULSE` | — |
| `Gateable` | — | — | `NXdetector.acquisition_mode=gated` | — | `GATE` | — |
| `Imageable` | — | — | `NXdetector` | — | — | `areaDetector` |
| `Streamable` | — | `EventAffordance` | — | — | — | `areaDetector NDPluginStream` |
| `FileWritable` | — | — | — | — | — | `areaDetector NDFileHDF5/TIFF` |
| `Bendable` | — | — | `NXmirror.bend_angle_x/y` | — | — | — |
| `EncoderInput` | `HW_IF_POSITION` (state) | `PropertyAffordance` (read) | — | — | `INENC` | — |
| `PulseGenerator` | — | — | — | — | `PGEN` | — |
| `Consumable` | — | — | material+thickness fields on NXmirror / NXattenuator / NXfilter / NXcrystal | — | — | — |

Note on **W3C SOSA inversion**: SOSA puts `-able` on the *property being acted on* (`ObservableProperty`, `ActuatableProperty`), CORA puts it on the *device that acts* (`Rotatable`). Both are coherent. When adapting to SOSA, translate `Rotatable` to `Rotation has type ActuatableProperty on this asset` rather than treating `Rotatable` and `Rotation` as the same noun.

## Catalog governance

- **Closed enum at v1.** Adding a value requires a CORA release; per-deployment extensions are not supported at this layer.
- **Add-only amendment path.** Never remove a published value. If a value becomes obsolete, deprecate it in docs and stop using it in new Family declarations — but the enum member stays for replay safety.
- **Banned pattern: `<noun>Selectable` / `<noun>Addressable`.** Parameter-selection items belong in `Family.settings_schema` or in an operations-layer `Capability` (DLM-B / phase 6k), not in `Affordance`. The grammatical test: "device supports being configured to set X" means settings_schema; "device supports doing X" means Affordance.
- **Contract per Affordance.** Each entry in the enum carries a one-line operational contract docstring inline at `cora.equipment.aggregates.family.affordance` (Bloch `Cloneable`-trap mitigation). The longer-form contract on this page is the authoritative reference for adapter authors.

## Related

- [Families](../catalog/families.md) — registered Families at the deployment level
- Capability vocabulary research (4-round, 11+ corpus) — section 5 of `project_capability_research` in user-memory
- DLM-A locks at `project_family_affordance_design` in user-memory
