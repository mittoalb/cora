"""Vertical slice for the `DiscardSubject` command.

Module-as-namespace surface:

    from cora.subject.features import discard_subject

    cmd = discard_subject.DiscardSubject(subject_id=...)
    handler = discard_subject.bind(deps)
    await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.subject.features.discard_subject import tool
from cora.subject.features.discard_subject.command import DiscardSubject
from cora.subject.features.discard_subject.decider import decide
from cora.subject.features.discard_subject.handler import Handler, bind
from cora.subject.features.discard_subject.route import router

__all__ = [
    "DiscardSubject",
    "Handler",
    "bind",
    "decide",
    "router",
    "tool",
]
