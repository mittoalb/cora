# Capabilities

*What the pilot leaves the beamline capable of.*

A pilot is worth doing only if it leaves the beamline in a different shape than it found it. Each item below is a capability 35-BM does not have today and that the pilot puts within reach.

## New sample classes without new scripting

Each Method named for the pilot is a re-usable shape. Adding a sample class that fits an existing Method (different rock, different alloy, different polymer) becomes a Practice and Plan binding, not a new script. The pace at which 35-BM can absorb new science stops being bounded by per-experiment Python.

## Strategy swaps where they matter

Center-of-rotation, ROI selection, segmentation, and alignment each become ports. Once one strategy lands at each port, others slot in without changing the surrounding workflow:

- New COR algorithms tested side by side on the same Run
- AI strategies promoted from experiment to default once they outperform manual on this beamline's data
- Manual fallback always available, audited identically

## Cross-experiment comparison

Today the dxfile `process` group is the closest thing to a re-runnable record. After the pilot, the event stream is the canonical record and `process` becomes a derived view. Cross-experiment queries (every scan with this lens, this COR strategy, this PI) become possible without grepping HDF5 files.

## Mail-in throughput

Subject custody removes the staff bottleneck on tracking samples between shipping label, beamline, and reconstruction. Beamtime that today goes to sample logistics goes to scans.

## Toward unattended CT

Each Decision strategy that proves itself is one fewer step that needs an operator at the console. The autonomous-CT vision (sample-in to volume-out without intervention) advances one strategy at a time, conditional on what each port proves at this beamline. Promotion happens on the beamline scientist's call, with the comparison events to back the decision. There is no fixed roadmap; the pilot earns the next step by what it actually demonstrates.
