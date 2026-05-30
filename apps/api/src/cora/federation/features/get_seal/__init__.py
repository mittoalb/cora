"""Vertical slice for the `GetSeal` query."""

from cora.federation.features.get_seal import tool
from cora.federation.features.get_seal.handler import Handler, SealView, bind
from cora.federation.features.get_seal.query import GetSeal
from cora.federation.features.get_seal.route import router

__all__ = ["GetSeal", "Handler", "SealView", "bind", "router", "tool"]
