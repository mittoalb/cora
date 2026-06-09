"""Vertical slice for the `AppendRunReadings` command.

Module-as-namespace surface:

    from cora.run.features import append_run_readings

    cmd = append_run_readings.AppendRunReadings(run_id=..., entries=(...,))
    handler = append_run_readings.bind(deps, reading_store=store)
    count = await handler(cmd, principal_id=..., correlation_id=...)

Lazy open-on-first-write: the handler emits
`RunReadingLogbookOpened` to the Run stream the first time a
reading is appended for a Run; subsequent appends find the logbook
already attached and skip the open-event emission. Mirrors Decision
BC's `append_inferences` precedent.
"""

from cora.run.features.append_run_readings import tool
from cora.run.features.append_run_readings.command import (
    AppendRunReadings,
    RunReadingInput,
)
from cora.run.features.append_run_readings.handler import Handler, bind
from cora.run.features.append_run_readings.route import router

__all__ = [
    "AppendRunReadings",
    "Handler",
    "RunReadingInput",
    "bind",
    "router",
    "tool",
]
