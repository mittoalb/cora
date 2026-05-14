"""Vertical slice for the `MountSubject` command.

Module-as-namespace surface:

    from cora.subject.features import mount_subject

    cmd = mount_subject.MountSubject(subject_id=..., asset_id=..., reason="")
    handler = mount_subject.bind(deps)
    await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.subject.features.mount_subject import tool
from cora.subject.features.mount_subject.command import MountSubject
from cora.subject.features.mount_subject.context import MountSubjectContext
from cora.subject.features.mount_subject.decider import decide
from cora.subject.features.mount_subject.handler import Handler, bind
from cora.subject.features.mount_subject.route import router

__all__ = [
    "Handler",
    "MountSubject",
    "MountSubjectContext",
    "bind",
    "decide",
    "router",
    "tool",
]
