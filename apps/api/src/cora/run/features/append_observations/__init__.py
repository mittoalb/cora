"""Vertical slice for the `AppendObservations` command.

Module-as-namespace surface:

    from cora.run.features import append_observations

    cmd = append_observations.AppendObservations(run_id=..., entries=(...,))
    handler = append_observations.bind(deps, observation_store=store)
    count = await handler(cmd, principal_id=..., correlation_id=...)

Lazy open-on-first-write: the handler emits
`RunObservationLogbookOpened` to the Run stream the first time a
observation is appended for a Run; subsequent appends find the logbook
already attached and skip the open-event emission. Mirrors Decision
BC's `append_inferences` precedent.
"""

from cora.run.features.append_observations import tool
from cora.run.features.append_observations.command import (
    AppendObservations,
    ObservationInput,
)
from cora.run.features.append_observations.handler import Handler, bind
from cora.run.features.append_observations.route import router

__all__ = [
    "AppendObservations",
    "Handler",
    "ObservationInput",
    "bind",
    "router",
    "tool",
]
