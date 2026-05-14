"""Vertical slice for the `DismountSubject` command (Phase 4f).

Module-as-namespace surface:

    from cora.subject.features import dismount_subject

    cmd = dismount_subject.DismountSubject(subject_id=..., reason="...")
    handler = dismount_subject.bind(deps)
    await handler(cmd, principal_id=..., correlation_id=...)

Phase 4f. Mirror of `mount_subject` in the inverse direction:
clears `Subject.mounted_on_asset_id` and returns status to
`Received`, enabling the multi-stage mount/dismount workflow that
the cross-aggregate-binding audit identified as missing in 4b.
Distinct from `remove_subject` (which is terminal-leading); this
slice is for "sample comes off the holder, ready for next mount".
"""

from cora.subject.features.dismount_subject import tool
from cora.subject.features.dismount_subject.command import DismountSubject
from cora.subject.features.dismount_subject.decider import decide
from cora.subject.features.dismount_subject.handler import Handler, bind
from cora.subject.features.dismount_subject.route import router

__all__ = [
    "DismountSubject",
    "Handler",
    "bind",
    "decide",
    "router",
    "tool",
]
