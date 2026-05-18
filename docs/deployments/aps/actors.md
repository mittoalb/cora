# Actors

*Access BC Actors that are conceptually facility-wide at APS.*

APS User Office accounts (proposal PIs), facility safety-process reviewers (ESRB, Beamline Scientists in review-chain capacity), the canonical APS Operator identity, and the AI Agent's co-registered Actor row. Beamline-bound staff (the 2-BM operator pool) live with their beamline. See [Model](../../architecture/model.md) for the aggregate shape.

| Actor | Kind |
| --- | --- |
| `APS Operator` | `human` |
| `Run Debrief` | `agent` |
| `APS Experiment Safety Review Board` | `human` |
| `2-BM Beamline Scientist` | `human` |
| `Proposal 2026-1234 PI` | `human` |
| `Proposal 2026-1235 PI` | `human` |
| `Proposal 2026-1236 PI` | `human` |
| `Proposal 2026-1237 PI` | `human` |
| `Sample-of-opportunity PI` | `human` |

## Pending

| Actor | Kind |
| --- | --- |
| Named APS scientific staff (cross-beamline duties) | `human` |
| Real ESRB membership (vs committee-as-actor) | `human` |
