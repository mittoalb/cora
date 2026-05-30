"""Aggregates owned by the Federation BC.

Three aggregates: `Permit`, `Credential`, `Seal`. `Permit` unifies
the prior outbound/inbound grant split behind a `direction`-tagged
terms union (`OutboundTerms | InboundTerms`) and carries a 4-state
FSM (Defined -> Active -> Suspended -> Revoked) shared across both
directions; `Credential` carries a rotation mini-FSM (Active ->
Rotating -> Active' + Revoked terminal); `Seal` is a per-facility
singleton (Live -> Republishing -> Live').
"""
