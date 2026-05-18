# Campaigns

*Campaign BC Campaigns registered at 2-BM.*

A Campaign composes Runs under a coordinated study, proposal-scoped and technique-tagged. See [Model](../../architecture/model.md) for the aggregate shape.

| Campaign | Intent | Runs |
| --- | --- | --- |
| `Proposal 2026-1234 beamtime` | `Coordinated` | 1234-A tomography |
| `Proposal 2026-1234 beamtime (degraded)` | `Coordinated` | 1234-A tomography (with intervention) |
| `Proposal 2026-1234 continuous-rotation series` | `Series` | continuous-rotation child Run {1..3}/3 |
| `Proposal 2026-1235 beamtime (aborted)` | `Coordinated` | 1235-B tomography (aborted) |
| `Proposal 2026-1236 2x2 tile mosaic` | `Coordinated` | mosaic tile {0..3} |
| `Proposal 2026-1237 multi-energy contrast study` | `Coordinated` | low-energy 25 keV, high-energy 30 keV |

## Pending

| Campaign | Intent | Runs |
| --- | --- | --- |
| Alignment-chain orchestration | `Coordinated` | alignment + calibration + Step-1 re-run |
| In-situ / operando study | `Coordinated` | |
| Energy sweep (N-point) | `Sweep` | |
| Block-design experiment | `Block` | |
