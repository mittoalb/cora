"""Vertical slice for the `StoreSubject` command.

Module-as-namespace surface:

    from cora.subject.features import store_subject

    cmd = store_subject.StoreSubject(subject_id=...)
    handler = store_subject.bind(deps)
    await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.subject.features.store_subject import tool
from cora.subject.features.store_subject.command import StoreSubject
from cora.subject.features.store_subject.decider import decide
from cora.subject.features.store_subject.handler import Handler, bind
from cora.subject.features.store_subject.route import router

__all__ = [
    "Handler",
    "StoreSubject",
    "bind",
    "decide",
    "router",
    "tool",
]
