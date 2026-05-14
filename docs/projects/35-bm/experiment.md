# Experiment

*One scan, walked end to end. Placeholder until the sample class is selected.*

When written, walks one full scan from proposal to delivered segmentation, naming events and Decision strategies at each step.

## Stages

| Stage | BC | Strategy port? |
| --- | --- | --- |
| Proposal and allocation | access | Review (committee / AI / hybrid) |
| Sample receipt | subject | None |
| Beamline alignment | equipment + run | Alignment (script / agent) |
| Practice binding | recipe + run | None |
| Sample loading | run | Manual or robot |
| Fly scan | run | None (deterministic) |
| Reconstruction and COR | decision + run | COR (TomoPy / AI / manual) |
| Denoising | data | None (deterministic) |
| Segmentation | decision | Segmentation (manual / interactive / model) |
| Delivery | data + access | None |

## Coverage

Exercises every BC, all four recipe-ladder layers, three Decision strategy ports, substream handling for high-frequency telemetry, cross-zone Conduits (Z3 → Z2 → Z1 → Z0). The audit trail lets a future operator re-derive deliverables from events alone.
