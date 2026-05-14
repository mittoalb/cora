# Scope

*What the pilot commits to, what it does not, and how each commit is judged.*

## Commits

Each commit names a primitive CORA brings to the beamline and the measurable form of "it works."

### Subsume scan orchestration

The `run` BC takes over [TomoScan](https://github.com/decarlof/tomoscan)'s role: PSO/FPGA triggering, encoder-referenced flat-field resync, angular sampling (Equally Spaced, Golden Angle, Van der Corput, TIMBIR). Audit moves from per-script logs into the canonical event store.

| | |
| --- | --- |
| Stress | A scan changes lens (1.1× → 5×) mid-Run; reconstruction stitches cleanly across the magnification change |
| Throughput | Scan-to-delivered-segmentation no worse than current manual workflow |

### Replayable scan audit

Every scan produces a complete event stream from proposal to delivered segmentation. Re-derivable from events alone, identical reconstruction output (modulo non-determinism captured in events).

| | |
| --- | --- |
| Reproducibility | A scan from N months ago re-derives byte-identically from its event stream, given the same inputs |

### Decision strategy interchangeability

COR finding, ROI selection, segmentation, and alignment are ports. Strategies plug in without changing surrounding workflow or audit shape.

| Step | Strategies | Returned event shape |
| --- | --- | --- |
| COR finding | TomoPy `find_center`, `find_center_pc`, `find_center_vo`, AI probability, manual | `CORDetermined { cor_pixel, strategy_id, confidence?, decision_id }` |
| ROI selection | Locator-CT, manual bounding box | `ROISelected { bbox, strategy_id, decision_id }` |
| Segmentation | Trained model, interactive labeling, manual | `SegmentationCompleted { mask_uri, strategy_id, model_id?, decision_id }` |
| Alignment | Scripted, alignment agent | `AlignmentCompleted { axis_state, strategy_id, decision_id }` |

| | |
| --- | --- |
| Strategy swap | Three COR strategies produce three `Decision` events, all auditable, all returning a `cor_pixel` |

### Sample chain of custody

Mail-in samples tracked from receipt through scan to disposal, attached to proposal and run.

| | |
| --- | --- |
| Locatability | A sample is locatable from any of: shipping label, proposal id, run id, dataset id, deliverable URI |

### High-rate telemetry as substream

Encoder readings at PSO trigger rate live in a per-Run telemetry channel that does not flow through the main event log; the main log stays projection-friendly.

| | |
| --- | --- |
| Throughput | Projection workers process a 1-min scan with 50,000+ telemetry samples without falling behind real time |

### Method reuse across configurations

A new objective, scintillator, or energy at the same beamline produces a new Practice for the same Method, without editing the Method.

| | |
| --- | --- |
| Reuse | The same Method binds to a fresh Practice when the lens, scintillator, or energy changes, without touching the Method definition |

## Does not

- **Replace TomoPy.** Reconstruction algorithms stay in TomoPy. CORA wraps them as Run steps and captures parameters as events.
- **Fully autonomous segmentation by default.** Segmentation is one of the interchangeable Decision ports. Autonomous is one option among manual, interactive, trained-model.
- **Real-time control loop.** The kHz encoder feedback loop stays in the FPGA and Aerotech controller. CORA observes and orchestrates; it does not sit in the trigger path.

## AI and autonomy

CORA's AI commitments are deliberately scoped: ports and audit, not specific intelligence. The pilot proves the swap mechanism, not the superiority of any one strategy.

### In scope

- **Decision ports** at COR, ROI, segmentation, alignment. Every result carries `strategy_id`, `model_id`, inputs, output, and confidence as a first-class event. Replayable.
- **Wrap what already works.** TomoPy COR variants, the existing probability-curve COR method, Locator-CT for ROI, Noise2Inverse360 for denoising, the rotation-axis alignment script. Nothing new is invented; what exists gets a uniform shape and an audit trail.
- **Agents as principals.** An AI strategy runs under its own identity, with the same authz and audit shape as a human operator. No special path.
- **Manual fallback always available** at every port. AI is one option among N, never the only option.

### Not in scope

- **No claim that AI outperforms manual** at any specific Decision. The port lets it be tested side by side; the pilot does not promise a winner.
- **No fully unattended sample-in to volume-out.** That is the long horizon, not the pilot deliverable.
- **No robot sample changing.** Hardware question, not CORA's scope.
- **No LLM-driven proposal triage.** Possible later as a Decision strategy, not promised here.
- **No per-experiment model retraining.** Approaches that need paired ground truth or per-deployment retraining do not survive contact with a production beamline.

### Stress

| | |
| --- | --- |
| Strategy comparability | COR Decision demonstrates three swappable strategies (TomoPy variant + probability method + manual) producing identical event shape |
| Agent as principal | The alignment script runs end-to-end as a non-human principal, full audit, no special-cased authz |
| Promotion | One strategy is promoted from experiment to default during the pilot, on the beamline scientist's call, with the comparison events to back it |

The bar for the pilot worked.
