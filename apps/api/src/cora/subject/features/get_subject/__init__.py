"""Vertical slice for the `GetSubject` query.

Module-as-namespace surface, symmetric with command slices:

    from cora.subject.features import get_subject

    q = get_subject.GetSubject(subject_id=...)
    handler = get_subject.bind(deps)
    subject = await handler(q, principal_id=..., correlation_id=...)
"""

from cora.subject.features.get_subject import tool
from cora.subject.features.get_subject.handler import Handler, bind
from cora.subject.features.get_subject.query import GetSubject
from cora.subject.features.get_subject.route import router

__all__ = [
    "GetSubject",
    "Handler",
    "bind",
    "router",
    "tool",
]
