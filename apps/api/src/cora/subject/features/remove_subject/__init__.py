"""Vertical slice for the `RemoveSubject` command.

Module-as-namespace surface:

    from cora.subject.features import remove_subject

    cmd = remove_subject.RemoveSubject(subject_id=...)
    handler = remove_subject.bind(deps)
    await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.subject.features.remove_subject import tool
from cora.subject.features.remove_subject.command import RemoveSubject
from cora.subject.features.remove_subject.decider import decide
from cora.subject.features.remove_subject.handler import Handler, bind
from cora.subject.features.remove_subject.route import router

__all__ = [
    "Handler",
    "RemoveSubject",
    "bind",
    "decide",
    "router",
    "tool",
]
