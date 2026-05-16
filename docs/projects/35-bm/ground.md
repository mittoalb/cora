# Ground

*What the pilot inherits at 35-BM. CORA wraps, observes, and audits; it does not replace.*

Aerotech, FPGA, EPICS, TomoPy, Polaris are mature, owned by other teams, and not on the table for replacement. Where ISA-95 strains against this reality is called out below.

## Assets

The ISA-95 backbone for 35-BM:

```
Enterprise: Argonne National Laboratory
└── Site: Advanced Photon Source (APS)
    └── Area: Imaging beamlines
        └── Unit: 35-BM
            └── Assembly: Tomo instrument
                ├── Aerotech Ensemble (rotation controller, PSO source)
                ├── softGlueZynq FPGA (Xilinx Zynq SoC, EPICS IOC)
                ├── Optique Peter triple-objective microscope
                │   ├── Mitutoyo objectives 1.1× / 5× / 10×
                │   └── LuAG scintillators 100 / 50 / 25 µm
                ├── FLIR Oryx ORX-10G-51S5M-C (2448 × 2048, 3.45 µm)
                ├── PCO Dimax HS (high-speed)
                └── Sample stage motors (X, Y, Z, pitch, roll)
```

Each Device is a candidate for a publication-quality persistent ID. The minting profile (PIDINST vs raw DataCite Instrument resourceType vs other) is deferred until the first Device needs to be cited externally; see [Deferred](../../stack/deferred.md). The Assembly is the unit of instrument calibration: an alignment is meaningless without naming the camera and lens together.

## Where ISA-95 strains

<div class="cora-aside" markdown>

- **Calibration as cross-Device entity.** A rotation-axis alignment is meaningful only when bound to a camera + lens. Calibration is a relationship across Devices; it needs its own aggregate.
- **Compute resources.** Polaris and H100 systems are Run-time resources the Asset hierarchy doesn't model. Separate Resource concept in the equipment BC.
- **Sub-assemblies.** The Optique Peter flattens into the parent Assembly today. Nested Assemblies may be needed.

</div>

## Software

Integrated through ports. Not replaced.

| Concern | Existing tool | CORA's role |
| --- | --- | --- |
| Reconstruction | [TomoPy](https://tomopy.readthedocs.io) | Wrap as a Run step; capture algorithm, parameters, COR strategy as events |
| Optics control | [mctOptics](https://mctoptics.readthedocs.io) | Equipment BC tracks lens and scintillator state |
| Data schema | dxfile / HDF5 | Data BC integrates; events table replaces the HDF5 `process` group as canonical |
| Denoising | [Noise2Inverse360](https://noise2inverse360.readthedocs.io) | Run as deterministic post-processing step |
| Hardware control | EPICS PVs | Trust BC's Conduit translates PV reads/writes at the facility boundary |
| Per-experiment summary | TomoLog | Candidate agent surface, generating run summaries from event streams |

## What CORA replaces

The `run` BC subsumes [TomoScan](https://github.com/decarlof/tomoscan)'s scan orchestration. PSO/FPGA triggering, encoder-referenced flat-field resync, angular sampling (Equally Spaced, Golden Angle, Van der Corput, TIMBIR) move from TomoScan's per-script Python into the Run aggregate as first-class events. TomoScan stays a reference; runtime moves to CORA.

## Trust topology

Per ISA-99 and IEC 62443:

| Zone | Population |
| --- | --- |
| Z3 (Enterprise / Lab) | Sample mailing logistics, proposal portal, user laptops |
| Z2 (Operations) | Control room workstations, shift coordination |
| Z1 (Control) | Beamline workstations (arcturus, lyra, tomo1), reconstruction servers (Polaris, EOS) |
| Z0 (Process) | EPICS network, Aerotech Ensemble, softGlueZynq FPGA, detector hardware |

Conduits cross zones with explicit policies:

- Z3 → Z2: proposal-granted access
- Z2 → Z1: shift assignments
- Z1 → Z0: PV writes (actuation), PV reads (observation)
- Z0 → Z1: trigger pulses (PSO), data streams (image frames)

EPICS PVs are the lingua franca. The Trust BC models the EPICS surface as a Conduit between Z1 and Z0. PV reads are observations; PV writes are actuations. Both are events. The Conduit policy answers: which principal can issue which PV write, when, with which audit trail. IEC 62443 framing preserved; CORA does not invent a new authorization model for facility hardware.

## Compute

Reconstruction runs across tiers depending on scan size:

- **Beamline workstations** (arcturus, lyra, tomo1): scan control, real-time preview, small reconstructions.
- **ALCF Polaris**: A100 GPUs; large mosaic and high-resolution.
- **NVIDIA H100 systems** (EOS): partnership compute, on- or off-network.

A benchmark scaled near-linearly: 54 min at 16 A100s, ~5 min at 128 H100s. CORA observes the compute job as a Run sub-step; it does not replace the scheduler.

## Where this beamline meets CORA

CORA's bounded contexts mapped to the imaging-pilot meaning at 35-BM. The codebase uses the left column; staff conversations use the right.

| BC | At 35-BM |
| --- | --- |
| `access` | Beamtime proposals, allocations, scheduling |
| `subject` | The sample (mail-in receipt, custody, link to runs, retention) |
| `equipment` | The tomo instrument and its devices: Aerotech stage, Optique Peter optics, FLIR/PCO detectors, softGlueZynq FPGA |
| `recipe` | Method/Practice catalog: phase-contrast micro-CT, nano-CT with FZP, MHz imaging |
| `run` | Scan Plans and Runs with full audit (encoder, FPGA pattern, lens changes, dropped frames) |
| `decision` | DecisionStrategy ports for COR, ROI, segmentation, alignment |
| `data` | Reconstructed volumes, segmentations, denoised outputs (dxfile/HDF5; events table is canonical) |
| `trust` | Zones (Z3/Z2/Z1/Z0) and Conduits (EPICS gateway, file transfer) |

For abstract patterns, see [Architecture](../../architecture/index.md).
