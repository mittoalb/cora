"""Vertical slice for the `GetCredential` query."""

from cora.federation.features.get_credential import tool
from cora.federation.features.get_credential.handler import (
    CredentialView,
    Handler,
    bind,
)
from cora.federation.features.get_credential.query import GetCredential
from cora.federation.features.get_credential.route import router

__all__ = ["CredentialView", "GetCredential", "Handler", "bind", "router", "tool"]
