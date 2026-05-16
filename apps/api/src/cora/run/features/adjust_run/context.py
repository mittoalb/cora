"""Cross-aggregate context the `adjust_run` decider validates against
(Phase 6j).

`RunAdjustContext` is built by the `adjust_run` handler from
`load_run` + `load_plan` + `load_practice` + `load_method` before
reaching the pure decider. The decider treats these loaded entities
as opaque domain data and validates without performing any I/O.

Mirrors `RunStartContext` (6f-1) shape. The Method's `parameters_schema`
is the only datum the decider needs from the upstream Recipe chain
(Run → Plan → Practice → Method); the schema is None when the
Method declares no contract (operator-responsibility territory per
the 6g-c schemaless semantic).

Slice-local module by design: only `adjust_run` uses this today.
"""

from dataclasses import dataclass
from typing import Any

from cora.run.aggregates.run import Run


@dataclass(frozen=True)
class RunAdjustContext:
    """Snapshot of upstream aggregate state at Run-adjust time.

    `run` is the source-state Run (the decider validates status
    and merges the patch against `run.effective_parameters`).
    `method_parameters_schema` is the Method's optional JSON Schema
    (None when the Method declares no contract; the decider then
    skips merged-result validation, mirroring 6g-c's schemaless
    semantic for steering of schemaless Methods).
    """

    run: Run
    method_parameters_schema: dict[str, Any] | None
