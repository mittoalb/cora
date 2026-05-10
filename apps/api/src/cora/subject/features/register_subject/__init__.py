"""Vertical slice for the `RegisterSubject` command.

Module-as-namespace surface:

    from cora.subject.features import register_subject

    cmd = register_subject.RegisterSubject(name="Sample-A1")
    handler = register_subject.bind(deps)
    subject_id = await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.subject.features.register_subject import tool
from cora.subject.features.register_subject.command import RegisterSubject
from cora.subject.features.register_subject.decider import decide
from cora.subject.features.register_subject.handler import (
    Handler,
    IdempotentHandler,
    bind,
)
from cora.subject.features.register_subject.route import router

__all__ = [
    "Handler",
    "IdempotentHandler",
    "RegisterSubject",
    "bind",
    "decide",
    "router",
    "tool",
]
