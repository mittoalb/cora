"""Vertical slice for the `AppendProcedureActivities` command.

Module-as-namespace surface:

    from cora.operation.features import append_activities

    cmd = append_activities.AppendProcedureActivities(
        procedure_id=..., entries=(...,)
    )
    handler = append_activities.bind(deps, step_store=store)
    count = await handler(cmd, principal_id=..., correlation_id=...)

Lazy open-on-first-write: the handler emits
`ProcedureActivitiesLogbookOpened` to the Procedure stream the first time
a step is appended for a Procedure; subsequent appends find the
logbook already attached and skip the open-event emission. Mirrors
Run BC's `append_observations` precedent (which mirrors Decision BC's
`append_inferences`).
"""

from cora.operation.features.append_activities import tool
from cora.operation.features.append_activities.command import (
    ActivityInput,
    AppendProcedureActivities,
)
from cora.operation.features.append_activities.handler import Handler, bind
from cora.operation.features.append_activities.route import router

__all__ = [
    "ActivityInput",
    "AppendProcedureActivities",
    "Handler",
    "bind",
    "router",
    "tool",
]
