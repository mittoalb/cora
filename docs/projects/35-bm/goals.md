# Goals

*What CORA commits to. What it does not. How success is measured.*

## Commits

- **Subsume scan orchestration.** The `run` BC takes over [TomoScan](https://github.com/decarlof/tomoscan)'s role: PSO/FPGA triggering, encoder-referenced flat-field resync, angular sampling (Equally Spaced, Golden Angle, Van der Corput, TIMBIR). Audit moves from per-script logs into the canonical event store.
- **Replayable scan audit.** Every scan produces a complete event stream from proposal to delivered segmentation. Re-derivable from events alone, identical reconstruction output (modulo non-determinism captured in events).
- **Decision strategy interchangeability.** COR-finding swaps between TomoPy `find_center_vo`, an AI probability method, or manual without changing workflow or audit shape.
- **Sample chain of custody.** Mail-in samples tracked from receipt through scan to disposal, attached to proposal and run.

## Does not

- **Replace TomoPy.** Reconstruction algorithms stay in TomoPy. CORA wraps them as Run steps and captures parameters as events.
- **Fully autonomous segmentation.** Strategies are interchangeable ports. Autonomous is one option among manual, interactive, trained-model.
- **Real-time control loop.** The kHz encoder feedback loop stays in the FPGA and Aerotech controller. CORA observes and orchestrates; it does not sit in the trigger path.

## Success

| Criterion | Measurement |
| --- | --- |
| End-to-end audit | Reconstruction byte-identical to manual run, given the same events |
| Strategy swap | Three COR strategies produce three `Decision` events, all auditable, all returning a `cor_pixel` |
| Sample tracking | A sample is locatable from any of: shipping label, proposal id, run id, dataset id |
| Throughput | Scan-to-delivered-segmentation no worse than current manual workflow |
| Reproducibility | A scan from N months ago can be re-derived from events without operator memory |

The bar for "the pilot worked", not the bar for "CORA is done".
