"""Cross-aggregate context the `promote_dataset` decider validates against.

`DatasetPromotionContext` is built by the `promote_dataset` handler from
`load_dataset` calls before reaching the pure decider. The decider
treats the loaded peer Datasets as opaque domain data and validates
the lineage-must-be-Production guard without performing any I/O.

Pattern: same shape as 6h's `PlanWireContext`, 6e-1's
`PlanBindingContext`, 6f-1's `RunStartContext`. Slice-local module
by design.

The handler loads each Dataset in `state.derived_from` to inspect
its current `intent`. Loading happens AFTER the existence + status
+ intent + Run-end-state guards (cheap rejections) so we don't pay
for derived_from loads when promotion would fail for a simpler
reason. See [[project_dataset_lineage_design]] §promote_dataset
slice §Decider validates.
"""

from dataclasses import dataclass
from uuid import UUID

from cora.data.aggregates.dataset import Dataset


@dataclass(frozen=True)
class DatasetPromotionContext:
    """Snapshot of upstream peer-Dataset state at promotion-validation time.

    `derived_from` is the loaded set of Datasets keyed by id. Always
    contains entries for every id in `state.derived_from` (the
    handler's load is exhaustive); the decider's lineage-integrity
    guard reads each entry's `intent` and rejects if any are still
    Trial.

    Empty when `state.derived_from` is empty (raw / standalone
    Datasets); the lineage-integrity guard is then skipped trivially.
    """

    derived_from: dict[UUID, Dataset]
