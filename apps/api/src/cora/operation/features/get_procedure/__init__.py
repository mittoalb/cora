"""Vertical slice for the `GetProcedure` query.

Module-as-namespace surface, symmetric with command slices:

    from cora.operation.features import get_procedure

    q = get_procedure.GetProcedure(procedure_id=...)
    handler = get_procedure.bind(deps)
    procedure = await handler(q, principal_id=..., correlation_id=...)
"""

from cora.operation.features.get_procedure import tool
from cora.operation.features.get_procedure.handler import Handler, bind
from cora.operation.features.get_procedure.query import GetProcedure
from cora.operation.features.get_procedure.route import router

__all__ = [
    "GetProcedure",
    "Handler",
    "bind",
    "router",
    "tool",
]
