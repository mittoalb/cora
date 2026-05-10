"""Vertical slice for the `ReturnSubject` command.

Module-as-namespace surface:

    from cora.subject.features import return_subject

    cmd = return_subject.ReturnSubject(subject_id=...)
    handler = return_subject.bind(deps)
    await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.subject.features.return_subject import tool
from cora.subject.features.return_subject.command import ReturnSubject
from cora.subject.features.return_subject.decider import decide
from cora.subject.features.return_subject.handler import Handler, bind
from cora.subject.features.return_subject.route import router

__all__ = [
    "Handler",
    "ReturnSubject",
    "bind",
    "decide",
    "router",
    "tool",
]
