"""Vertical slice for the `MeasureSubject` command.

Module-as-namespace surface:

    from cora.subject.features import measure_subject

    cmd = measure_subject.MeasureSubject(subject_id=...)
    handler = measure_subject.bind(deps)
    await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.subject.features.measure_subject import tool
from cora.subject.features.measure_subject.command import MeasureSubject
from cora.subject.features.measure_subject.decider import decide
from cora.subject.features.measure_subject.handler import Handler, bind
from cora.subject.features.measure_subject.route import router

__all__ = [
    "Handler",
    "MeasureSubject",
    "bind",
    "decide",
    "router",
    "tool",
]
