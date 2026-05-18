"""Affordance closed StrEnum: device-level operational primitives a Family supports.

Phase 5j. Per DLM-A [[family-affordance-design-phases-5i-5j-lock]] and
the 4-round Stage 0 research [[project-capability-research]]:

- An Affordance is a CLAIM about what the device can do, set-membership-
  shaped (a Family `affords` Rotatable iff Rotatable is in
  Family.affordances). Matches type-class membership semantics (Swift
  API Design Guidelines / .NET Framework Design Guidelines / Java
  java.lang / Python collections.abc / W3C SOSA ObservableProperty).
- 28 starter items in 3 explicit patterns:
    A. Action affordances (`-able` suffix): "device supports doing X"
       — 24 items across Motion / Imaging / Triggering / Streaming /
       Optics+Environment / Reporting.
    B. Signal affordances (noun): "device exposes signal X" — 3 items.
    C. Lifecycle affordances (noun): "device has lifecycle property X"
       — 1 item.
- Closed v1 enum. Add-only amendment path (never remove a published
  value). New values land via additive evolution; renames require the
  Marten/Axon dual-match dance and are explicitly out of scope at v1.

## Why three patterns, not one

The dominant computing-vocabulary convention is `-able` for capability
claims (Swift codifies it, .NET endorses it, Java/Python/Ruby follow
informally). Action affordances follow this rule cleanly. But some
device properties are NOT actions:
  - `EncoderInput` / `EncoderOutput` / `PulseGenerator` are SIGNALS the
    device exposes (data-flow shape, not "device supports doing X").
  - `Consumable` is a LIFECYCLE property (passive parts that get
    swapped, like the LuAG scintillator screen).

Forcing `Encodable` or `Consumeable` would violate the read-aloud
test ([[project-naming-conventions]] R1) and conceal the semantic
difference. The mixed surface is honest, not a bug. See
[[project-capability-research]] section 5a for the full precedent
chain + the pre-empted critiques (Rust terseness rejection / AAS
noun-only divergence / Bloch Cloneable trap).

## Drops vs the original v1 list

The Round 4 verification pass dropped 5 parameter-shaped candidates
that belong elsewhere:
  - `BitDepthSelectable`, `ROIConfigurable`, `BadPixelMaskable` →
    `Family.settings_schema` (parameter values, not actions).
  - `BraggAddressable`, `EnergySelectable` → operations-layer
    `Capability` (DLM-B / phase 6k), not Affordance.
The grammatical test: if the candidate reads as "device supports
being configured to set <noun>", it's parameter-shaped, not action-
shaped. Compound `<noun>Selectable` / `<noun>Addressable` is the
foot-gun pattern; banned at code review per
[[project-capability-research]] anti-hook 21.

## Contract per affordance

Each Affordance carries a one-line operational-contract docstring
(Bloch `Cloneable`-trap mitigation per
[[project-capability-research]] anti-hook 23). The contract names
what a device promises when it claims the affordance — not just a
description but a behavior commitment that downstream code can rely
on. Longer-form per-affordance reference docs live in
`docs/reference/affordances.md`.

## Cross-vocabulary mapping

Adapter authors (ros2_control, W3C WoT TD, NeXus, OPC UA LADS,
PandABox, EPICS, areaDetector, SOSA) cross-walk via the mapping
table in `CONTRIBUTING.md` alongside the enum definition. SOSA's
key pattern inversion is documented there: SOSA puts `-able` on the
*property being acted on* (`ObservableProperty`), CORA puts it on
the *device that acts* (`Rotatable`). Both coherent.
"""

from enum import StrEnum


class Affordance(StrEnum):
    """Device-level operational primitive. Closed v1 enum (28 items, 3 patterns).

    Values are PascalCase strings so they serialize naturally as JSON
    discriminators without translation.

    Pattern A — Action affordances (`-able` / `-ible`):
        "device supports doing X". Set-membership claim. 24 items.

    Pattern B — Signal affordances (noun):
        "device exposes signal X". Data-flow shape. 3 items.

    Pattern C — Lifecycle affordances (noun):
        "device has lifecycle property X". 1 item.
    """

    # ---------- Pattern A: Action affordances ----------
    # Motion (8)
    ROTATABLE = "Rotatable"
    """Device supports a rotational degree of freedom with a set position command."""
    TRANSLATABLE = "Translatable"
    """Device supports a linear (single-axis) degree of freedom with a set position command."""
    HOMEABLE = "Homeable"
    """`home` operation drives to a reference position and zeros the encoder."""
    LIMITABLE = "Limitable"
    """Honors operator-configured software-limit min/max bounds; refuses motion past them."""
    POSITION_TRIGGERABLE = "PositionTriggerable"
    """Emits trigger pulses when its encoder crosses configured positions (PandA `PCOMP`)."""
    POSITION_CAPTURABLE = "PositionCapturable"
    """Latches encoder values into a buffer on external trigger edges (PandA `PCAP`)."""
    POSABLE = "Posable"
    """Accepts a coordinated multi-DOF pose command (6-DOF X/Y/Z/U/V/W) referred
    to a configurable pivot/tool/work frame; for hexapods + parallel kinematics."""
    INDEXABLE = "Indexable"
    """Finite enumerated set of mutually-exclusive named positions with a `go to
    named position` operation (filter wheel, mirror coating stripe, monochromator)."""

    # Imaging (2)
    IMAGEABLE = "Imageable"
    """Acquires 2D image frames on exposure/trigger; supports basic capture."""
    BINNABLE = "Binnable"
    """Supports on-sensor pixel binning (NxN combining) to trade resolution for SNR/speed."""

    # Triggering and timing (3)
    TRIGGERABLE = "Triggerable"
    """Accepts an external edge trigger to start a single timed operation."""
    GATEABLE = "Gateable"
    """Integrates over the duration of an external level signal (gate high = active)."""
    SYNCHRONIZABLE = "Synchronizable"
    """Aligns its internal clock to an external master clock or sync signal."""

    # Streaming and data (4)
    STREAMABLE = "Streamable"
    """Pushes data continuously over a transport without per-frame request/response."""
    PRE_TRIGGER_BUFFERABLE = "PreTriggerBufferable"
    """Internal ring buffer with configurable pre/post-trigger split; on trigger,
    the past N frames are preserved."""
    COMPRESSIBLE = "Compressible"
    """Applies a lossless or lossy codec to outgoing data (JPEG, LZ4, etc.) at runtime."""
    FILE_WRITABLE = "FileWritable"
    """Writes acquired data to a file path the operator configures (HDF5, TIFF, etc.)."""

    # Optics and environment (5)
    COOLABLE = "Coolable"
    """Exposes a setpoint for its thermal control loop (sensor cooling, etc.)."""
    PID_CONTROLLABLE = "PIDControllable"
    """Control loop exposes P/I/D gains for operator tuning."""
    SHUTTERABLE = "Shutterable"
    """Has an open/close shutter that the operator can command."""
    ATTENUABLE = "Attenuable"
    """Reduces the intensity of an incident beam by an operator-set factor."""
    BENDABLE = "Bendable"
    """Optical surface (mirror) has actively-driven curvature/figure (mechanical
    bender, bimorph piezo array, thermal); see NXmirror `bend_angle_x/y`."""

    # Reporting (2)
    IDENTIFIABLE = "Identifiable"
    """Returns a persistent identifier (serial number, MAC, etc.) on query."""
    REPORTABLE = "Reportable"
    """Returns a health/status reading on query (temperature, error count, etc.)."""

    # ---------- Pattern B: Signal affordances (noun) ----------
    ENCODER_INPUT = "EncoderInput"
    """Accepts an external encoder signal as its position feedback source."""
    ENCODER_OUTPUT = "EncoderOutput"
    """Emits its position as an encoder signal that downstream devices can read."""
    PULSE_GENERATOR = "PulseGenerator"
    """Generates configurable digital pulse trains (width, period, count) for timing."""

    # ---------- Pattern C: Lifecycle affordances (noun) ----------
    CONSUMABLE = "Consumable"
    """Passive part whose identity, material, thickness, lot, and install/remove
    history are operationally tracked, even though it has no command surface
    (scintillator screens, filters, sample holders, target foils)."""


class InvalidAffordanceError(ValueError):
    """The supplied affordance value is not a member of the closed `Affordance` enum.

    Defensive guard for direct in-process callers (sagas, tests,
    fixtures). REST + MCP boundaries catch this via Pydantic
    enum validation first, returning HTTP 422 / MCP error before
    this exception fires.
    """

    def __init__(self, value: object) -> None:
        super().__init__(
            f"Invalid Affordance value: {value!r}; must be one of the 28 "
            f"closed-enum members (see cora.equipment.aggregates.family.affordance)"
        )
        self.value = value


__all__ = ["Affordance", "InvalidAffordanceError"]
