# Features

*Features stress-tested at the pilot, with measurable success criteria.*

Each targets a CORA primitive and an imaging pain point.

## Telemetry substreams

| | |
| --- | --- |
| Primitive | Substream-per-Run for kHz-rate device data |
| Pain | Encoder readings at PSO trigger rate can't share the main events table without choking projection workers |
| Success | Projection workers process a 1-min scan with 50,000+ telemetry samples without falling behind real time |

## Streaming Run

| | |
| --- | --- |
| Primitive | Run FSM with `held`/`resumed`, plus equipment-change events mid-Run |
| Pain | Optique Peter zoom-in during streaming reconstruction needs flat-field refresh and angle resync without restarting |
| Success | A scan changes lens (1.1× → 5×) mid-Run; reconstruction stitches cleanly across the magnification change |

## COR strategy port

| | |
| --- | --- |
| Primitive | Interchangeable strategies returning identical event shapes |
| Pain | COR algorithm choice is workflow-critical, varies per sample, today hard-coded per script |
| Success | Three strategies (TomoPy `find_center_vo`, AI probability, manual) selectable by config; each emits `CORDetermined` with the same schema |

## Sample custody

| | |
| --- | --- |
| Primitive | `subject` BC with Sample aggregate |
| Pain | Mail-in samples lose context between shipping label, beamline, reconstruction |
| Success | A sample is locatable from any of: shipping label, proposal id, run id, dataset id, deliverable URI |

## Method portability (deferred to MAX IV)

| | |
| --- | --- |
| Primitive | Recipe ladder Method/Practice split |
| Pain | Per-facility scripts duplicate the same physics with different brand names |
| Success | A Method named at 35-BM binds to a Practice at MAX IV without modifying the Method |

## Replayable audit

| | |
| --- | --- |
| Primitive | Event sourcing with principal-on-every-event |
| Pain | Reproducing a scan from N months ago needs operator memory + tribal knowledge. The dxfile `process` group captures only `tomopy.conf` and `tomo_scan.conf`. |
| Success | An N-months-old scan re-derives byte-identically from its event stream, given the same inputs |

These determine whether the pilot proves CORA's design. Other features (visualization, notification, dashboards) are valuable but not load-bearing.
